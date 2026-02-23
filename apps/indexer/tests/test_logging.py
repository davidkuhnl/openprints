"""Tests for openprints.common.utils.logging."""

from __future__ import annotations

import json
import logging
import sys
from io import StringIO

import openprints.common.utils.logging as logging_mod
from openprints.common.utils.logging import configure_logging


def test_configure_logging_text_format_includes_extra(monkeypatch) -> None:
    monkeypatch.setattr(logging_mod, "_LOGGING_CONFIGURED", False)
    monkeypatch.setenv("OPENPRINTS_LOG_FORMAT", "text")
    monkeypatch.setenv("OPENPRINTS_LOG_LEVEL", "INFO")
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
