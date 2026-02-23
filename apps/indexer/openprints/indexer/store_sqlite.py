"""SQLite-backed index store. Tables: design_versions (history), designs (current)."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from .store import DesignCurrentRow, DesignVersionRow

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS design_versions (
    event_id TEXT PRIMARY KEY,
    pubkey TEXT NOT NULL,
    design_id TEXT NOT NULL,
    kind INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    name TEXT,
    format TEXT,
    sha256 TEXT,
    url TEXT,
    content TEXT,
    raw_event_json TEXT NOT NULL,
    received_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS designs (
    pubkey TEXT NOT NULL,
    design_id TEXT NOT NULL,
    latest_event_id TEXT NOT NULL,
    latest_published_at INTEGER NOT NULL,
    first_published_at INTEGER NOT NULL,
    first_seen_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    version_count INTEGER NOT NULL,
    name TEXT,
    format TEXT,
    sha256 TEXT,
    url TEXT,
    content TEXT,
    tags_json TEXT NOT NULL,
    PRIMARY KEY (pubkey, design_id),
    FOREIGN KEY (latest_event_id) REFERENCES design_versions(event_id)
);
"""


class SQLiteIndexStore:
    """Index store that persists to SQLite. Tables: design_versions, designs."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def open(self) -> None:
        """Open the database connection and ensure tables exist."""
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(str(self._path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        logger.info("sqlite_store_opened", extra={"path": str(self._path)})

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is None:
            return
        await self._conn.close()
        self._conn = None
        logger.debug("sqlite_store_closed", extra={"path": str(self._path)})

    def _conn_required(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteIndexStore not open; call open() first")
        return self._conn

    async def upsert_design_version(self, row: DesignVersionRow) -> None:
        conn = self._conn_required()
        await conn.execute(
            """
            INSERT OR REPLACE INTO design_versions (
                event_id, pubkey, design_id, kind, created_at,
                name, format, sha256, url, content, raw_event_json, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.event_id,
                row.pubkey,
                row.design_id,
                row.kind,
                row.created_at,
                row.name,
                row.format,
                row.sha256,
                row.url,
                row.content,
                row.raw_event_json,
                row.received_at,
            ),
        )
        await conn.commit()

    async def upsert_design_current(self, row: DesignCurrentRow) -> None:
        conn = self._conn_required()
        await conn.execute(
            """
            INSERT OR REPLACE INTO designs (
                pubkey, design_id, latest_event_id, latest_published_at,
                first_published_at, first_seen_at, updated_at, version_count,
                name, format, sha256, url, content, tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.pubkey,
                row.design_id,
                row.latest_event_id,
                row.latest_published_at,
                row.first_published_at,
                row.first_seen_at,
                row.updated_at,
                row.version_count,
                row.name,
                row.format,
                row.sha256,
                row.url,
                row.content,
                row.tags_json,
            ),
        )
        await conn.commit()
