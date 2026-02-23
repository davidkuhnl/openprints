"""Minimal HTTP health server for the indexer (stdlib only).

Serves GET /health (liveness) and GET /ready (readiness) with JSON responses.
/ready checks DB (if configured) and relay connectivity (if configured).
Runs in a daemon thread so it does not block the indexer event loop.
When Phase 3 adds the FastAPI API, this can be replaced by the same
/health and /ready endpoints on the API so callers keep the same contract.
"""

from __future__ import annotations

import json
import logging
import socket
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

HEALTH_BODY = json.dumps({"status": "ok", "service": "indexer"}).encode("utf-8")
READY_OK_BODY = json.dumps({"status": "ok", "ready": True}).encode("utf-8")
READY_TIMEOUT = 2.0


def _check_db(database_path: str) -> str | None:
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


def _check_relays(relay_urls: list[str]) -> str | None:
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


def _make_handler() -> type[BaseHTTPRequestHandler]:
    """Build a handler class that serves /health and /ready."""

    class _HealthHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            path = self.path.split("?")[0].rstrip("/") or "/"
            if path == "/health":
                self._send_json(200, HEALTH_BODY)
            elif path == "/ready":
                self._ready()
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"not found"}')

        def _ready(self) -> None:
            db_path = getattr(self.server, "database_path", None)
            relay_urls = getattr(self.server, "relay_urls", None) or []
            db_err = _check_db(db_path) if db_path else None
            relay_err = _check_relays(relay_urls) if relay_urls else None
            if db_err or relay_err:
                body = json.dumps(
                    {
                        "status": "error",
                        "ready": False,
                        "database": db_err,
                        "relays": relay_err,
                    }
                ).encode("utf-8")
                self._send_json(503, body)
            else:
                self._send_json(200, READY_OK_BODY)

        def _send_json(self, code: int, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            logger.debug("health_server %s", args[0] if args else "")

    return _HealthHandler


def start_health_server(
    port: int,
    *,
    database_path: str | None = None,
    relay_urls: list[str] | None = None,
) -> HTTPServer:
    """Start a minimal HTTP server for GET /health and GET /ready in a daemon thread.

    Binds to the given port (e.g. 8080). /ready checks database_path (sync SELECT 1)
    and relay_urls (TCP connect to each relay host:port) when provided.
    Returns the server instance so the caller can call stop_health_server(server).
    """
    handler = _make_handler()
    server = HTTPServer(("", port), handler)
    server.database_path = database_path  # type: ignore[attr-defined]
    server.relay_urls = relay_urls or []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("health_server_start port=%s", port)
    return server


def stop_health_server(server: HTTPServer) -> None:
    """Shut down the health server and release the port."""
    port = server.server_address[1]
    server.shutdown()
    logger.info("health_server_stop port=%s", port)
