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

    async def ensure_identity_pending(self, pubkey: str, first_seen_at: int) -> None:
        # Step 3 is log-only seeding for now; DB upsert arrives in step 4.
        logger.info(
            "ensure_identity_pending_todo",
            extra={"pubkey": pubkey, "first_seen_at": first_seen_at},
        )

    async def list_designs(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        order: str = "latest_published_at_desc",
        name_contains: str | None = None,
    ) -> tuple[list[DesignCurrentRow], int]:
        """List current designs with optional filters. Returns (rows, total_count)."""
        conn = self._conn_required()
        order_col = "latest_published_at"
        order_dir = "DESC"
        if order == "first_published_at_desc":
            order_col, order_dir = "first_published_at", "DESC"
        elif order == "first_published_at_asc":
            order_col, order_dir = "first_published_at", "ASC"
        elif order == "latest_published_at_asc":
            order_col, order_dir = "latest_published_at", "ASC"
        # default: latest_published_at_desc

        where = "WHERE 1=1"
        params: list[object] = []
        if name_contains and name_contains.strip():
            where += " AND name LIKE ?"
            params.append(f"%{name_contains.strip()}%")

        async with conn.execute(f"SELECT COUNT(*) FROM designs {where}", params) as cur:
            (total,) = await cur.fetchone()

        params_ext = list(params) + [limit, offset]
        async with conn.execute(
            f"""
            SELECT pubkey, design_id, latest_event_id, latest_published_at,
                   first_published_at, first_seen_at, updated_at, version_count,
                   name, format, sha256, url, content, tags_json
            FROM designs {where}
            ORDER BY {order_col} {order_dir}
            LIMIT ? OFFSET ?
            """,
            params_ext,
        ) as cur:
            rows = await cur.fetchall()

        result = [
            DesignCurrentRow(
                pubkey=r["pubkey"],
                design_id=r["design_id"],
                latest_event_id=r["latest_event_id"],
                latest_published_at=r["latest_published_at"],
                first_published_at=r["first_published_at"],
                first_seen_at=r["first_seen_at"],
                updated_at=r["updated_at"],
                version_count=r["version_count"],
                name=r["name"],
                format=r["format"],
                sha256=r["sha256"],
                url=r["url"],
                content=r["content"],
                tags_json=r["tags_json"],
            )
            for r in rows
        ]
        return result, total

    async def get_design(self, pubkey: str, design_id: str) -> DesignCurrentRow | None:
        """Return the current design row for (pubkey, design_id), or None."""
        conn = self._conn_required()
        async with conn.execute(
            """
            SELECT pubkey, design_id, latest_event_id, latest_published_at,
                   first_published_at, first_seen_at, updated_at, version_count,
                   name, format, sha256, url, content, tags_json
            FROM designs WHERE pubkey = ? AND design_id = ?
            """,
            (pubkey, design_id),
        ) as cur:
            r = await cur.fetchone()
        if r is None:
            return None
        return DesignCurrentRow(
            pubkey=r["pubkey"],
            design_id=r["design_id"],
            latest_event_id=r["latest_event_id"],
            latest_published_at=r["latest_published_at"],
            first_published_at=r["first_published_at"],
            first_seen_at=r["first_seen_at"],
            updated_at=r["updated_at"],
            version_count=r["version_count"],
            name=r["name"],
            format=r["format"],
            sha256=r["sha256"],
            url=r["url"],
            content=r["content"],
            tags_json=r["tags_json"],
        )

    async def get_counts(self) -> tuple[int, int]:
        """Return (designs_count, versions_count) for stats."""
        conn = self._conn_required()
        async with conn.execute("SELECT COUNT(*) FROM designs") as cur:
            (designs_count,) = await cur.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM design_versions") as cur:
            (versions_count,) = await cur.fetchone()
        return designs_count, versions_count
