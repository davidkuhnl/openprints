"""Tests for openprints.indexer.health_checks (used by API /ready)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from openprints.indexer.health_checks import (
    _relay_host_port,
    check_db,
    check_relays,
)


def test_check_db_returns_none_when_reachable() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        import sqlite3

        sqlite3.connect(db_path).close()
        assert check_db(db_path) is None
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_check_db_returns_error_when_unreachable() -> None:
    err = check_db("/nonexistent/dir/db.db")
    assert err is not None
    assert "unable" in err or "nonexistent" in err or "No such" in err or "Error" in err


def test_relay_host_port_parses_ws_url() -> None:
    assert _relay_host_port("ws://localhost:7447") == ("localhost", 7447)
    assert _relay_host_port("ws://relay.example.org:80") == ("relay.example.org", 80)


def test_relay_host_port_parses_wss_url() -> None:
    assert _relay_host_port("wss://relay.example:443") == ("relay.example", 443)
    assert _relay_host_port("wss://secure.example") == ("secure.example", 443)


def test_relay_host_port_ws_without_port_defaults_to_80() -> None:
    assert _relay_host_port("ws://host") == ("host", 80)


def test_relay_host_port_returns_none_for_invalid() -> None:
    assert _relay_host_port("") is None
    assert _relay_host_port("not-a-url") is None


def test_check_relays_returns_none_when_empty_list() -> None:
    assert check_relays([]) is None


def test_check_relays_returns_error_for_invalid_url() -> None:
    err = check_relays(["not-a-url"])
    assert err is not None
    assert "invalid" in err.lower()
