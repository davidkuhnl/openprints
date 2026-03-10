"""Readiness check helpers: DB and relay connectivity. Used by the API /ready endpoint."""

from __future__ import annotations

import socket
import sqlite3
from urllib.parse import urlparse

READY_TIMEOUT = 2.0


def check_db(database_path: str) -> str | None:
    """Return None if DB is reachable, else an error message."""
    try:
        conn = sqlite3.connect(database_path, timeout=READY_TIMEOUT)
        conn.execute("SELECT 1")
        conn.close()
        return None
    except Exception as e:
        return str(e)


def _relay_host_port(relay_url: str) -> tuple[str, int] | None:
    """Parse ws:// or wss:// URL to (host, port). Return None if invalid."""
    try:
        parsed = urlparse(relay_url)
        host = parsed.hostname or ""
        port = parsed.port
        if not host:
            return None
        if port is None:
            port = 443 if parsed.scheme == "wss" else 80
        return (host, port)
    except Exception:
        return None


def check_relays(relay_urls: list[str]) -> str | None:
    """Return None if at least one relay is reachable (TCP), else an error message."""
    errors: list[str] = []
    for url in relay_urls:
        hp = _relay_host_port(url)
        if not hp:
            errors.append(f"{url}: invalid URL")
            continue
        host, port = hp
        try:
            sock = socket.create_connection((host, port), timeout=READY_TIMEOUT)
            sock.close()
            return None
        except OSError as e:
            errors.append(f"{url}: {e}")
    return "; ".join(errors) if errors else None


def ready_checks(db_path: str | None, relay_urls: list[str]) -> dict[str, str]:
    """Compute readiness checks for database and relays."""
    db_result: str
    if db_path:
        db_err = check_db(db_path)
        db_result = "ok" if db_err is None else db_err
    else:
        db_result = "not_configured"

    relay_result: str
    if relay_urls:
        relay_err = check_relays(relay_urls)
        relay_result = "ok" if relay_err is None else relay_err
    else:
        relay_result = "not_configured"

    return {"database": db_result, "relays": relay_result}
