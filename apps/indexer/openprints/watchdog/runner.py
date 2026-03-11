from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from argparse import Namespace
from pathlib import Path
from typing import Callable

from openprints.common.errors import invalid_value
from openprints.common.utils.logging import configure_logging
from openprints.common.utils.output import print_json

logger = logging.getLogger(__name__)
_TELEGRAM_BOT_TOKEN = "OPENPRINTS_WATCHDOG_TELEGRAM_BOT_TOKEN"
_TELEGRAM_CHAT_ID = "OPENPRINTS_WATCHDOG_TELEGRAM_CHAT_ID"
_WATCHDOG_ENV_FILE = ".env.watchdog"


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
    telegram = _build_telegram_notifier(Path.cwd() / _WATCHDOG_ENV_FILE)

    child_cmd = [sys.executable, "-m", "openprints", mode]
    config = str(getattr(args, "config", "") or "").strip()
    if config:
        child_cmd.extend(["--config", config])
    child_args = list(getattr(args, "child_args", []) or [])
    if child_args and child_args[0] == "--":
        child_args = child_args[1:]
    child_cmd.extend(child_args)

    restart_attempt = 0
    child: subprocess.Popen[bytes] | None = None
    stop_requested = False
    stop_signal: int | None = None

    def _on_signal(signum, _frame) -> None:
        nonlocal stop_requested, stop_signal
        stop_requested = True
        stop_signal = signum
        if child is not None and child.poll() is None:
            logger.info("watchdog_forward_signal", extra={"signal": signum, "child_pid": child.pid})
            telegram.send(
                "watchdog_forward_signal",
                {"mode": mode, "child_pid": child.pid, "signal": signum},
            )
            child.terminate()

    prev_sigint = signal.signal(signal.SIGINT, _on_signal)
    prev_sigterm = signal.signal(signal.SIGTERM, _on_signal)

    try:
        while True:
            if stop_requested:
                return _shutdown_child(child)

            child = subprocess.Popen(child_cmd)
            logger.info(
                "watchdog_child_started",
                extra={
                    "mode": mode,
                    "child_pid": child.pid,
                    "restart_attempt": restart_attempt,
                    "max_restarts": max_restarts,
                },
            )
            telegram.send(
                "watchdog_child_started",
                {
                    "mode": mode,
                    "child_pid": child.pid,
                    "restart_attempt": restart_attempt,
                    "max_restarts": max_restarts,
                },
            )

            while True:
                exit_code = child.poll()
                if exit_code is None:
                    if stop_requested:
                        return _shutdown_child(child)
                    time.sleep(poll_interval_s)
                    continue

                if stop_requested:
                    logger.info(
                        "watchdog_child_stopped",
                        extra={
                            "mode": mode,
                            "child_pid": child.pid,
                            "exit_code": exit_code,
                            "signal": stop_signal,
                        },
                    )
                    telegram.send(
                        "watchdog_child_stopped",
                        {
                            "mode": mode,
                            "child_pid": child.pid,
                            "exit_code": exit_code,
                            "signal": stop_signal,
                        },
                    )
                    return 0
                level_fn = logger.info if exit_code == 0 else logger.warning
                level_fn(
                    "watchdog_child_exited",
                    extra={"mode": mode, "child_pid": child.pid, "exit_code": exit_code},
                )
                telegram.send(
                    "watchdog_child_exited",
                    {"mode": mode, "child_pid": child.pid, "exit_code": exit_code},
                )
                if restart_attempt >= max_restarts:
                    logger.error(
                        "watchdog_restart_limit_reached",
                        extra={
                            "mode": mode,
                            "restart_attempt": restart_attempt,
                            "max_restarts": max_restarts,
                        },
                    )
                    telegram.send(
                        "watchdog_restart_limit_reached",
                        {
                            "mode": mode,
                            "restart_attempt": restart_attempt,
                            "max_restarts": max_restarts,
                        },
                    )
                    return 1

                delay_s = min(backoff_initial_s * (2**restart_attempt), backoff_max_s)
                restart_attempt += 1
                logger.info(
                    "watchdog_restart_scheduled",
                    extra={
                        "mode": mode,
                        "restart_attempt": restart_attempt,
                        "backoff_s": delay_s,
                    },
                )
                telegram.send(
                    "watchdog_restart_scheduled",
                    {"mode": mode, "restart_attempt": restart_attempt, "backoff_s": delay_s},
                )
                if not _sleep_with_stop(delay_s, lambda: stop_requested):
                    return _shutdown_child(child)
                break
    finally:
        signal.signal(signal.SIGINT, prev_sigint)
        signal.signal(signal.SIGTERM, prev_sigterm)


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


class _TelegramNotifier:
    def __init__(self, token: str | None, chat_id: str | None) -> None:
        self._token = (token or "").strip()
        self._chat_id = (chat_id or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self._token and self._chat_id)

    def send(self, event: str, fields: dict[str, object]) -> None:
        if not self.enabled:
            return
        text = _format_telegram_message(event, fields)
        body = urllib.parse.urlencode({"chat_id": self._chat_id, "text": text}).encode("utf-8")
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        request = urllib.request.Request(url=url, data=body, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=5):
                return
        except Exception as exc:
            logger.warning(
                "watchdog_telegram_send_failed", extra={"error": str(exc), "event": event}
            )


def _build_telegram_notifier(env_path: Path) -> _TelegramNotifier:
    env_file_values = _load_env_file(env_path)
    token = env_file_values.get(_TELEGRAM_BOT_TOKEN) or os.environ.get(_TELEGRAM_BOT_TOKEN)
    chat_id = env_file_values.get(_TELEGRAM_CHAT_ID) or os.environ.get(_TELEGRAM_CHAT_ID)
    notifier = _TelegramNotifier(token=token, chat_id=chat_id)
    if notifier.enabled:
        logger.info("watchdog_telegram_enabled", extra={"env_file": str(env_path)})
    else:
        logger.info(
            "watchdog_telegram_disabled",
            extra={"env_file": str(env_path), "reason": "missing_token_or_chat_id"},
        )
    return notifier


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip("'").strip('"')
    return values


def _format_telegram_message(event: str, fields: dict[str, object]) -> str:
    details = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
    return f"openprints_watchdog {event} {details}".strip()
