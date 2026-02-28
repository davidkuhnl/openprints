"""FastAPI dependencies: config, store, readiness context."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from openprints.common.settings import build_runtime_settings
from openprints.indexer.store_sqlite import SQLiteIndexStore

# Module-level store and config for lifespan (open/close store with app).
_store: SQLiteIndexStore | None = None
_db_path: str | None = None
_relay_urls: list[str] = []


def get_api_config():
    """Load app config for API (database path, relay_urls for /ready)."""
    settings, errors, _ = build_runtime_settings()
    if errors:
        return None, errors
    if settings is None:
        return None, [{"message": "failed to build runtime settings"}]
    return {
        "database_path": settings.database_path,
        "relay_urls": list(settings.relay_urls),
    }, None


async def open_store(app: FastAPI) -> None:
    """Lifespan: open SQLite store if database_path is configured."""
    global _store, _db_path, _relay_urls
    cfg, errs = get_api_config()
    if errs or not cfg:
        _store = None
        _db_path = None
        _relay_urls = []
        return
    _db_path = cfg["database_path"]
    _relay_urls = cfg["relay_urls"] or []
    if not _db_path:
        _store = None
        return
    path = Path(_db_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    store = SQLiteIndexStore(str(path))
    await store.open()
    _store = store


async def close_store(app: FastAPI) -> None:
    """Lifespan: close store."""
    global _store
    if _store is not None:
        await _store.close()
        _store = None


def get_store() -> SQLiteIndexStore | None:
    """Return the opened SQLite store, or None if not configured."""
    return _store


def get_ready_context() -> tuple[str | None, list[str]]:
    """Return (database_path, relay_urls) for /ready checks."""
    return _db_path, _relay_urls
