"""Tests for openprints.common.utils.logging."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from io import StringIO

import openprints.common.utils.logging as logging_mod
from openprints.common.utils.logging import configure_logging


def test_configure_logging_text_format_includes_extra(monkeypatch) -> None:
    monkeypatch.setattr(logging_mod, "_LOGGING_CONFIGURED", False)
    monkeypatch.setenv("OPENPRINTS_LOG_FORMAT", "text")
    monkeypatch.setenv("OPENPRINTS_LOG_LEVEL", "INFO")
    monkeypatch.delenv("OPENPRINTS_LOG_FOLDER", raising=False)
    monkeypatch.delenv("OPENPRINTS_LOG_BASE_NAME", raising=False)
    stderr = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    configure_logging()
    logger = logging.getLogger("test_logging")
    logger.info("test_message", extra={"key": "value", "num": 42})

    out = stderr.getvalue()
    assert "test_message" in out
    assert "key=value" in out or "num=42" in out


def test_configure_logging_json_format_includes_extra(monkeypatch) -> None:
    monkeypatch.setattr(logging_mod, "_LOGGING_CONFIGURED", False)
    monkeypatch.setenv("OPENPRINTS_LOG_FORMAT", "json")
    monkeypatch.setenv("OPENPRINTS_LOG_LEVEL", "INFO")
    monkeypatch.delenv("OPENPRINTS_LOG_FOLDER", raising=False)
    monkeypatch.delenv("OPENPRINTS_LOG_BASE_NAME", raising=False)
    stderr = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    configure_logging()
    logger = logging.getLogger("test_logging_json")
    logger.info("json_message", extra={"relay": "ws://r:7447", "count": 1})

    out = stderr.getvalue()
    data = json.loads(out.strip())
    assert data.get("message") == "json_message"
    assert data.get("relay") == "ws://r:7447"
    assert data.get("count") == 1


def test_configure_logging_idempotent(monkeypatch) -> None:
    monkeypatch.setattr(logging_mod, "_LOGGING_CONFIGURED", False)
    monkeypatch.setenv("OPENPRINTS_LOG_LEVEL", "WARNING")
    stderr = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    configure_logging()
    root = logging.getLogger()
    handler_count = len(root.handlers)
    configure_logging()
    assert len(root.handlers) == handler_count


def test_configure_logging_writes_hourly_file_with_pid_base_and_window(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(logging_mod, "_LOGGING_CONFIGURED", False)
    monkeypatch.setenv("OPENPRINTS_LOG_FORMAT", "text")
    monkeypatch.setenv("OPENPRINTS_LOG_LEVEL", "INFO")
    monkeypatch.setenv("OPENPRINTS_LOG_FOLDER", str(tmp_path))
    monkeypatch.setenv("OPENPRINTS_LOG_BASE_NAME", "indexer")
    stderr = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    configure_logging()
    logger = logging.getLogger("test_logging_file")
    logger.info("file_message")

    pid = logging_mod.os.getpid()
    expected_name = f"indexer-{pid}-"
    files = list(tmp_path.glob("*.log"))
    assert len(files) == 1
    assert expected_name in files[0].name
    assert "file_message" in files[0].read_text(encoding="utf-8")
    assert stderr.getvalue() == ""


def test_configure_logging_rolls_at_top_of_hour(monkeypatch, tmp_path) -> None:
    class _FakeDateTime:
        current = datetime(2026, 3, 11, 10, 45, 0, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls.current
            return cls.current.astimezone(tz)

    monkeypatch.setattr(logging_mod, "datetime", _FakeDateTime)
    monkeypatch.setattr(logging_mod, "_LOGGING_CONFIGURED", False)
    monkeypatch.setenv("OPENPRINTS_LOG_FORMAT", "text")
    monkeypatch.setenv("OPENPRINTS_LOG_LEVEL", "INFO")
    monkeypatch.setenv("OPENPRINTS_LOG_FOLDER", str(tmp_path))
    monkeypatch.setenv("OPENPRINTS_LOG_BASE_NAME", "indexer")
    stderr = StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    configure_logging()
    logger = logging.getLogger("test_logging_rollover")
    logger.info("before_roll")
    _FakeDateTime.current = datetime(2026, 3, 11, 11, 0, 0, tzinfo=UTC)
    logger.info("after_roll")

    pid = logging_mod.os.getpid()
    file_one = tmp_path / f"indexer-{pid}-20260311T1000-20260311T1100.log"
    file_two = tmp_path / f"indexer-{pid}-20260311T1100-20260311T1200.log"
    assert file_one.exists()
    assert file_two.exists()
    assert "before_roll" in file_one.read_text(encoding="utf-8")
    assert "after_roll" in file_two.read_text(encoding="utf-8")
