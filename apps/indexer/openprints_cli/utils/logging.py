from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime

_LOGGING_CONFIGURED = False
_BASE_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _BASE_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    level_name = os.environ.get("OPENPRINTS_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    log_format = os.environ.get("OPENPRINTS_LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler(sys.stderr)
    if log_format == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    _LOGGING_CONFIGURED = True
