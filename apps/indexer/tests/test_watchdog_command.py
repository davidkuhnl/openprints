from __future__ import annotations

import sys
from argparse import Namespace

import pytest

import openprints.watchdog.runner as watchdog_runner


@pytest.fixture(autouse=True)
def _disable_telegram_for_watchdog_tests(monkeypatch) -> None:
    """
    Prevent accidental live Telegram messaging during watchdog-related tests.

    The watchdog runner constructs its Telegram notifier from both environment
    variables and an optional `.env.watchdog` file in the current working
    directory. We disable it for all tests by overriding
    `openprints.watchdog.runner.build_telegram_notifier`.
    """

    # Ensure any environment-based configuration is ignored.
    monkeypatch.setenv("OPENPRINTS_WATCHDOG_TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("OPENPRINTS_WATCHDOG_TELEGRAM_CHAT_ID", "")

    def _disabled_build_telegram_notifier(_env_path):
        return watchdog_runner._TelegramNotifier(token=None, chat_id=None)

    monkeypatch.setattr(
        watchdog_runner, "build_telegram_notifier", _disabled_build_telegram_notifier
    )


class _FakeChild:
    def __init__(self, pid: int, exit_code: int) -> None:
        self.pid = pid
        self._exit_code = exit_code

    def poll(self):
        return self._exit_code

    def terminate(self) -> None:
        return

    def wait(self, timeout=None):
        return self._exit_code

    def kill(self) -> None:
        return


class _FakeChildSeq:
    def __init__(self, pid: int, polls: list[int | None]) -> None:
        self.pid = pid
        self._polls = polls
        self._idx = 0
        self.terminated = False

    def poll(self):
        if self._idx >= len(self._polls):
            return self._polls[-1]
        value = self._polls[self._idx]
        self._idx += 1
        return value

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout=None):
        return -15

    def kill(self) -> None:
        return


def _args(**overrides: object) -> Namespace:
    base = {
        "mode": "index",
        "config": None,
        "max_restarts": 0,
        "backoff_initial_s": 1.0,
        "backoff_max_s": 30.0,
        "poll_interval_s": 1.0,
        "log_level": "INFO",
        "child_args": [],
    }
    base.update(overrides)
    return Namespace(**base)


def test_watchdog_restarts_child_with_backoff_and_stops_at_limit(monkeypatch) -> None:
    launched: list[list[str]] = []
    children = [_FakeChild(111, 2), _FakeChild(222, 2)]

    def _fake_popen(cmd):
        launched.append(list(cmd))
        return children.pop(0)

    monkeypatch.setattr(watchdog_runner, "configure_logging", lambda: None)
    monkeypatch.setattr(watchdog_runner.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(watchdog_runner, "_sleep_with_stop", lambda _d, _s: True)
    monkeypatch.setattr(watchdog_runner.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("OPENPRINTS_LOG_FOLDER", "/tmp/logs")
    monkeypatch.setenv("OPENPRINTS_LOG_BASE_NAME", "indexer")

    rc = watchdog_runner.run_watchdog(
        _args(
            mode="index",
            config="openprints.toml",
            max_restarts=1,
            log_level="DEBUG",
            child_args=["--", "--design-duration-s", "1.0"],
        )
    )

    assert rc == 1
    assert watchdog_runner.os.environ.get("OPENPRINTS_LOG_LEVEL") == "DEBUG"
    assert watchdog_runner.os.environ.get("OPENPRINTS_LOG_FOLDER") is None
    assert watchdog_runner.os.environ.get("OPENPRINTS_LOG_BASE_NAME") is None
    assert launched == [
        [
            sys.executable,
            "-m",
            "openprints",
            "index",
            "--config",
            "openprints.toml",
            "--design-duration-s",
            "1.0",
        ],
        [
            sys.executable,
            "-m",
            "openprints",
            "index",
            "--config",
            "openprints.toml",
            "--design-duration-s",
            "1.0",
        ],
    ]


def test_watchdog_runs_serve_mode_child(monkeypatch) -> None:
    launched: list[list[str]] = []

    def _fake_popen(cmd):
        launched.append(list(cmd))
        return _FakeChild(333, 1)

    monkeypatch.setattr(watchdog_runner, "configure_logging", lambda: None)
    monkeypatch.setattr(watchdog_runner.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(watchdog_runner.signal, "signal", lambda *_args, **_kwargs: None)

    rc = watchdog_runner.run_watchdog(_args(mode="serve", max_restarts=0))

    assert rc == 1
    assert launched == [[sys.executable, "-m", "openprints", "serve"]]


def test_watchdog_rejects_invalid_restart_settings(capsys) -> None:
    rc = watchdog_runner.run_watchdog(_args(max_restarts=-1))
    assert rc == 1
    out = capsys.readouterr().out
    assert "max_restarts" in out


def test_watchdog_logs_expected_stop_when_signal_forwarded(monkeypatch) -> None:
    handlers: dict[int, object] = {}
    original_signal = watchdog_runner.signal.signal
    child = _FakeChildSeq(444, [None, -15])
    info_events: list[str] = []
    warning_events: list[str] = []

    def _fake_signal(sig, handler):
        handlers[sig] = handler
        return original_signal

    def _fake_popen(_cmd):
        return child

    signaled = {"done": False}

    def _fake_sleep(_secs):
        if not signaled["done"]:
            signaled["done"] = True
            handlers[watchdog_runner.signal.SIGINT](watchdog_runner.signal.SIGINT, None)

    monkeypatch.setattr(watchdog_runner, "configure_logging", lambda: None)
    monkeypatch.setattr(watchdog_runner.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(watchdog_runner.signal, "signal", _fake_signal)
    monkeypatch.setattr(watchdog_runner.time, "sleep", _fake_sleep)
    monkeypatch.setattr(
        watchdog_runner.logger, "info", lambda msg, **kwargs: info_events.append(msg)
    )
    monkeypatch.setattr(
        watchdog_runner.logger, "warning", lambda msg, **kwargs: warning_events.append(msg)
    )

    rc = watchdog_runner.run_watchdog(_args(mode="serve", max_restarts=0))

    assert rc == 0
    assert "watchdog_child_stopped" in info_events
    assert "watchdog_child_exited" not in warning_events


def test_load_env_file_parses_values(tmp_path) -> None:
    env_path = tmp_path / ".env.watchdog"
    env_path.write_text(
        "\n".join(
            [
                "# comment",
                "OPENPRINTS_WATCHDOG_TELEGRAM_BOT_TOKEN=abc:token",
                'OPENPRINTS_WATCHDOG_TELEGRAM_CHAT_ID="12345"',
            ]
        ),
        encoding="utf-8",
    )
    values = watchdog_runner._load_env_file(env_path)
    assert values["OPENPRINTS_WATCHDOG_TELEGRAM_BOT_TOKEN"] == "abc:token"
    assert values["OPENPRINTS_WATCHDOG_TELEGRAM_CHAT_ID"] == "12345"


def test_telegram_notifier_sends_message(monkeypatch) -> None:
    calls: list[str] = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout):
        calls.append(str(request.full_url))
        return _Resp()

    monkeypatch.setattr(watchdog_runner.urllib.request, "urlopen", _fake_urlopen)
    notifier = watchdog_runner._TelegramNotifier(token="tkn", chat_id="42")
    notifier.send("watchdog_child_started", {"mode": "serve", "child_pid": 123})
    assert len(calls) == 1
    assert "https://api.telegram.org/bottkn/sendMessage" in calls[0]
