from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TextIO

_LOGGING_CONFIGURED = False
_BASE_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())


class _TextFormatter(logging.Formatter):
    """Formatter that appends extra= key/value pairs to the log line."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = [
            f"{k}={v}"
            for k, v in sorted(record.__dict__.items())
            if k not in _BASE_RECORD_FIELDS and not k.startswith("_")
        ]
        if not extras:
            return base
        return base + " " + " ".join(extras)


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


def _hour_window_start(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def _hour_window_bounds(ts: datetime) -> tuple[datetime, datetime]:
    start = _hour_window_start(ts)
    return start, start + timedelta(hours=1)


def _build_hourly_log_filename(base_name: str, pid: int, ts: datetime) -> str:
    start, end = _hour_window_bounds(ts)
    return f"{base_name}-{pid}-{start:%Y%m%dT%H00}-{end:%Y%m%dT%H00}.log"


class _HourlyWindowFileHandler(logging.Handler):
    """Write logs to files named by hour window and rotate at top-of-hour."""

    def __init__(self, folder: str, base_name: str, pid: int) -> None:
        super().__init__()
        self._folder = Path(folder)
        self._folder.mkdir(parents=True, exist_ok=True)
        self._base_name = base_name
        self._pid = pid
        self._window_start: datetime | None = None
        self._stream: TextIO | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            now = datetime.now(UTC)
            self._open_stream_for(now)
            if self._stream is None:
                return
            message = self.format(record)
            self._stream.write(message + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        finally:
            super().close()

    def _open_stream_for(self, now: datetime) -> None:
        window_start = _hour_window_start(now)
        if self._stream is not None and self._window_start == window_start:
            return
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        file_name = _build_hourly_log_filename(self._base_name, self._pid, now)
        path = self._folder / file_name
        self._stream = path.open("a", encoding="utf-8")
        self._window_start = window_start


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    level_name = os.environ.get("OPENPRINTS_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    log_format = os.environ.get("OPENPRINTS_LOG_FORMAT", "text").lower()
    log_folder = os.environ.get("OPENPRINTS_LOG_FOLDER", "").strip()
    log_base_name = os.environ.get("OPENPRINTS_LOG_BASE_NAME", "").strip()

    formatter: logging.Formatter
    if log_format == "json":
        formatter = _JsonFormatter()
    else:
        formatter = _TextFormatter(
            "%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    root_logger = logging.getLogger()
    for existing in list(root_logger.handlers):
        root_logger.removeHandler(existing)
        existing.close()
    if log_folder and log_base_name:
        file_handler = _HourlyWindowFileHandler(log_folder, log_base_name, os.getpid())
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    else:
        stderr_handler: logging.Handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(formatter)
        root_logger.addHandler(stderr_handler)
    root_logger.setLevel(level)
    _LOGGING_CONFIGURED = True
