"""Tests for openprints.indexer.health_server."""

from __future__ import annotations

import json
import tempfile
import urllib.request
from pathlib import Path

from openprints.indexer.health_server import (
    _check_db,
    _check_relays,
    _relay_host_port,
    start_health_server,
    stop_health_server,
)


def _get(port: int, path: str) -> tuple[int, bytes]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    with urllib.request.urlopen(req, timeout=2) as resp:
        return (resp.status, resp.read())


def _get_error(port: int, path: str, timeout: float = 2) -> tuple[int, bytes] | None:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (resp.status, resp.read())
    except urllib.error.HTTPError as e:
        return (e.code, e.read())
    except OSError:
        return None


def test_health_and_ready_and_404_one_server() -> None:
    """One server start for /health, /ready (no config), and 404 to reduce overhead."""
    server = start_health_server(0)
    port = server.server_address[1]
    try:
        status, body = _get(port, "/health")
        assert status == 200
        assert json.loads(body.decode("utf-8")) == {"status": "ok", "service": "indexer"}
        status, body = _get(port, "/ready")
        assert status == 200
        assert json.loads(body.decode("utf-8")) == {"status": "ok", "ready": True}
        result = _get_error(port, "/other")
        assert result is not None
        assert result[0] == 404
        assert "error" in json.loads(result[1].decode("utf-8"))
    finally:
        stop_health_server(server)


def test_ready_200_when_db_reachable() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        import sqlite3

        sqlite3.connect(db_path).execute("SELECT 1").close()
        server = start_health_server(0, database_path=db_path)
        port = server.server_address[1]
        try:
            status, body = _get(port, "/ready")
            assert status == 200
            data = json.loads(body.decode("utf-8"))
            assert data == {"status": "ok", "ready": True}
        finally:
            stop_health_server(server)
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_ready_503_when_db_unreachable() -> None:
    server = start_health_server(0, database_path="/nonexistent/path/to/db.db")
    port = server.server_address[1]
    try:
        result = _get_error(port, "/ready")
        assert result is not None
        status, body = result
        assert status == 503
        data = json.loads(body.decode("utf-8"))
        assert data["status"] == "error"
        assert data["ready"] is False
        assert "database" in data
        assert data["database"] is not None
    finally:
        stop_health_server(server)


def test_ready_503_when_no_relay_reachable() -> None:
    server = start_health_server(
        0,
        relay_urls=["ws://127.0.0.1:19999"],
    )
    port = server.server_address[1]
    try:
        result = _get_error(port, "/ready")
        assert result is not None
        status, body = result
        assert status == 503
        data = json.loads(body.decode("utf-8"))
        assert data["status"] == "error"
        assert data["ready"] is False
        assert "relays" in data
        assert data["relays"] is not None
    finally:
        stop_health_server(server)


def test_stop_health_server_releases_port() -> None:
    server = start_health_server(0)
    port = server.server_address[1]
    stop_health_server(server)
    # Short timeout: we expect connection to fail (refused or reset) quickly.
    result = _get_error(port, "/health", timeout=0.2)
    assert result is None


def test_check_db_returns_none_when_reachable() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        import sqlite3

        sqlite3.connect(db_path).close()
        assert _check_db(db_path) is None
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_check_db_returns_error_when_unreachable() -> None:
    err = _check_db("/nonexistent/dir/db.db")
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
    assert _check_relays([]) is None


def test_check_relays_returns_error_for_invalid_url() -> None:
    err = _check_relays(["not-a-url"])
    assert err is not None
    assert "invalid" in err.lower()
