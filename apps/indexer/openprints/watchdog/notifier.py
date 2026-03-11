from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_TELEGRAM_BOT_TOKEN = "OPENPRINTS_WATCHDOG_TELEGRAM_BOT_TOKEN"
_TELEGRAM_CHAT_ID = "OPENPRINTS_WATCHDOG_TELEGRAM_CHAT_ID"


class TelegramNotifier:
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


def build_telegram_notifier(env_path: Path) -> TelegramNotifier:
    env_file_values = _load_env_file(env_path)
    token = env_file_values.get(_TELEGRAM_BOT_TOKEN) or os.environ.get(_TELEGRAM_BOT_TOKEN)
    chat_id = env_file_values.get(_TELEGRAM_CHAT_ID) or os.environ.get(_TELEGRAM_CHAT_ID)
    notifier = TelegramNotifier(token=token, chat_id=chat_id)
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
