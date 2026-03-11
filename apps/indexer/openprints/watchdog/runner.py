from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from openprints.common.errors import invalid_value
from openprints.common.utils.logging import configure_logging
from openprints.common.utils.output import print_json
from openprints.watchdog import notifier as _telegram_notifier
from openprints.watchdog.notifier import TelegramNotifier, build_telegram_notifier

logger = logging.getLogger(__name__)
_WATCHDOG_ENV_FILE = ".env.watchdog"

# Backward-compatible aliases for older tests/imports.
_TelegramNotifier = TelegramNotifier
_build_telegram_notifier = build_telegram_notifier
_load_env_file = _telegram_notifier._load_env_file
_format_telegram_message = _telegram_notifier._format_telegram_message
urllib = _telegram_notifier.urllib


@dataclass
class _WatchdogConfig:
    mode: str
    child_cmd: list[str]
    max_restarts: int
    backoff_initial_s: float
    backoff_max_s: float
    poll_interval_s: float
    telegram: TelegramNotifier


class _WatchdogRunner:
    def __init__(self, config: _WatchdogConfig) -> None:
        self._config = config
        self._restart_attempt = 0
        self._child: subprocess.Popen[bytes] | None = None
        self._stop_requested = False
        self._stop_signal: int | None = None
        self._prev_sigint = None
        self._prev_sigterm = None

    def run(self) -> int:
        self._prev_sigint = signal.signal(signal.SIGINT, self._on_signal)
        self._prev_sigterm = signal.signal(signal.SIGTERM, self._on_signal)
        try:
            while True:
                if self._stop_requested:
                    return _shutdown_child(self._child)

                self._start_child_process()
                result = self._watch_child_process()
                if result is not None:
                    return result
        finally:
            signal.signal(signal.SIGINT, self._prev_sigint)
            signal.signal(signal.SIGTERM, self._prev_sigterm)

    def _on_signal(self, signum, _frame) -> None:
        self._stop_requested = True
        self._stop_signal = signum
        if self._child is not None and self._child.poll() is None:
            logger.info(
                "watchdog_forward_signal", extra={"signal": signum, "child_pid": self._child.pid}
            )
            self._config.telegram.send(
                "watchdog_forward_signal",
                {"mode": self._config.mode, "child_pid": self._child.pid, "signal": signum},
            )
            self._child.terminate()

    def _start_child_process(self) -> None:
        self._child = subprocess.Popen(self._config.child_cmd)
        logger.info(
            "watchdog_child_started",
            extra={
                "mode": self._config.mode,
                "child_pid": self._child.pid,
                "restart_attempt": self._restart_attempt,
                "max_restarts": self._config.max_restarts,
            },
        )
        self._config.telegram.send(
            "watchdog_child_started",
            {
                "mode": self._config.mode,
                "child_pid": self._child.pid,
                "restart_attempt": self._restart_attempt,
                "max_restarts": self._config.max_restarts,
            },
        )

    def _watch_child_process(self) -> int | None:
        while True:
            # Child is guaranteed to exist after _start_child_process in run().
            if self._child is None:
                return 1

            exit_code = self._child.poll()
            if exit_code is None:
                if self._stop_requested:
                    return _shutdown_child(self._child)
                time.sleep(self._config.poll_interval_s)
                continue

            if self._stop_requested:
                logger.info(
                    "watchdog_child_stopped",
                    extra={
                        "mode": self._config.mode,
                        "child_pid": self._child.pid,
                        "exit_code": exit_code,
                        "signal": self._stop_signal,
                    },
                )
                self._config.telegram.send(
                    "watchdog_child_stopped",
                    {
                        "mode": self._config.mode,
                        "child_pid": self._child.pid,
                        "exit_code": exit_code,
                        "signal": self._stop_signal,
                    },
                )
                return 0

            level_fn = logger.info if exit_code == 0 else logger.warning
            level_fn(
                "watchdog_child_exited",
                extra={
                    "mode": self._config.mode,
                    "child_pid": self._child.pid,
                    "exit_code": exit_code,
                },
            )
            self._config.telegram.send(
                "watchdog_child_exited",
                {"mode": self._config.mode, "child_pid": self._child.pid, "exit_code": exit_code},
            )

            if self._restart_attempt >= self._config.max_restarts:
                logger.error(
                    "watchdog_restart_limit_reached",
                    extra={
                        "mode": self._config.mode,
                        "restart_attempt": self._restart_attempt,
                        "max_restarts": self._config.max_restarts,
                    },
                )
                self._config.telegram.send(
                    "watchdog_restart_limit_reached",
                    {
                        "mode": self._config.mode,
                        "restart_attempt": self._restart_attempt,
                        "max_restarts": self._config.max_restarts,
                    },
                )
                return 1

            delay_s = min(
                self._config.backoff_initial_s * (2**self._restart_attempt),
                self._config.backoff_max_s,
            )
            self._restart_attempt += 1
            logger.info(
                "watchdog_restart_scheduled",
                extra={
                    "mode": self._config.mode,
                    "restart_attempt": self._restart_attempt,
                    "backoff_s": delay_s,
                },
            )
            self._config.telegram.send(
                "watchdog_restart_scheduled",
                {
                    "mode": self._config.mode,
                    "restart_attempt": self._restart_attempt,
                    "backoff_s": delay_s,
                },
            )
            if not _sleep_with_stop(delay_s, lambda: self._stop_requested):
                return _shutdown_child(self._child)
            return None


def run_watchdog(args: Namespace) -> int:
    mode = str(getattr(args, "mode", "") or "").strip().lower()
    if mode not in {"index", "serve"}:
        print_json({"ok": False, "errors": [invalid_value("mode", "mode must be index or serve")]})
        return 1

    max_restarts = int(getattr(args, "max_restarts", 5))
    backoff_initial_s = float(getattr(args, "backoff_initial_s", 1.0))
    backoff_max_s = float(getattr(args, "backoff_max_s", 30.0))
    poll_interval_s = float(getattr(args, "poll_interval_s", 1.0))
    if max_restarts < 0:
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("max_restarts", "max_restarts must be >= 0")],
            }
        )
        return 1
    if backoff_initial_s <= 0 or backoff_max_s <= 0 or poll_interval_s <= 0:
        print_json(
            {
                "ok": False,
                "errors": [
                    invalid_value(
                        "watchdog",
                        "backoff_initial_s, backoff_max_s, and poll_interval_s must be > 0",
                    )
                ],
            }
        )
        return 1

    # Watchdog logs always go to console using OpenPrints formatter.
    log_level = str(getattr(args, "log_level", "") or "").strip()
    os.environ["OPENPRINTS_LOG_LEVEL"] = log_level.upper() if log_level else "INFO"
    os.environ.pop("OPENPRINTS_LOG_FOLDER", None)
    os.environ.pop("OPENPRINTS_LOG_BASE_NAME", None)
    configure_logging()
    telegram = build_telegram_notifier(Path.cwd() / _WATCHDOG_ENV_FILE)

    child_cmd = [sys.executable, "-m", "openprints", mode]
    config = str(getattr(args, "config", "") or "").strip()
    if config:
        child_cmd.extend(["--config", config])
    child_args = list(getattr(args, "child_args", []) or [])
    if child_args and child_args[0] == "--":
        child_args = child_args[1:]
    child_cmd.extend(child_args)

    config_obj = _WatchdogConfig(
        mode=mode,
        child_cmd=child_cmd,
        max_restarts=max_restarts,
        backoff_initial_s=backoff_initial_s,
        backoff_max_s=backoff_max_s,
        poll_interval_s=poll_interval_s,
        telegram=telegram,
    )
    return _WatchdogRunner(config_obj).run()


def _sleep_with_stop(duration_s: float, stop_requested: Callable[[], bool]) -> bool:
    end = time.monotonic() + duration_s
    while time.monotonic() < end:
        if stop_requested():
            return False
        time.sleep(min(0.2, end - time.monotonic()))
    return True


def _shutdown_child(child: subprocess.Popen[bytes] | None) -> int:
    if child is None or child.poll() is not None:
        return 0
    child.terminate()
    try:
        child.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5.0)
    return 0
