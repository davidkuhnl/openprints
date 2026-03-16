"""SQLite-backed index store. Tables: design_versions, designs, identities."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from .store import DesignCurrentRow, DesignVersionRow

logger = logging.getLogger(__name__)

_IDENTITY_COLUMNS = (
    "pubkey",
    "status",
    "pubkey_first_seen_at",
    "pubkey_last_seen_at",
    "name",
    "display_name",
    "about",
    "picture",
    "shape",
    "banner",
    "website",
    "nip05",
    "lud06",
    "lud16",
    "profile_raw_json",
    "profile_fetched_at",
    "fetch_last_attempt_at",
    "retry_count",
)

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

CREATE TABLE IF NOT EXISTS identities (
    pubkey TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('pending', 'fetched', 'failed')),
    pubkey_first_seen_at INTEGER NOT NULL,
    pubkey_last_seen_at INTEGER NOT NULL,
    name TEXT,
    display_name TEXT,
    about TEXT,
    picture TEXT,
    shape TEXT,
    banner TEXT,
    website TEXT,
    nip05 TEXT,
    lud06 TEXT,
    lud16 TEXT,
    profile_raw_json TEXT,
    profile_fetched_at INTEGER,
    fetch_last_attempt_at INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0
);
"""


class SQLiteIndexStore:
    """Index store that persists to SQLite. Tables: design_versions, designs, identities."""

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
        await self._ensure_identity_schema()
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

    async def _ensure_identity_schema(self) -> None:
        """Apply lightweight additive schema changes for identities."""
        conn = self._conn_required()
        async with conn.execute("PRAGMA table_info(identities)") as cur:
            rows = await cur.fetchall()
        existing_columns = {str(row["name"]) for row in rows}
        if "shape" not in existing_columns:
            await conn.execute("ALTER TABLE identities ADD COLUMN shape TEXT")

    async def append_design_version(self, row: DesignVersionRow) -> bool:
        """Insert design version once; return False when event_id already exists."""
        conn = self._conn_required()
        cursor = await conn.execute(
            """
            INSERT OR IGNORE INTO design_versions (
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
        return int(cursor.rowcount or 0) == 1

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
        conn = self._conn_required()
        await conn.execute(
            """
            INSERT INTO identities (
                pubkey, status, pubkey_first_seen_at, pubkey_last_seen_at, retry_count
            ) VALUES (?, 'pending', ?, ?, 0)
            ON CONFLICT(pubkey) DO UPDATE SET
                pubkey_last_seen_at = excluded.pubkey_last_seen_at
            """,
            (pubkey, first_seen_at, first_seen_at),
        )
        await conn.commit()

    async def list_identity_pubkeys_for_refresh(
        self, *, limit: int, stale_after_s: int, now_ts: int
    ) -> list[str]:
        conn = self._conn_required()
        stale_cutoff = now_ts - stale_after_s
        async with conn.execute(
            """
            SELECT pubkey, status, fetch_last_attempt_at, retry_count, profile_fetched_at
            FROM identities
            WHERE status IN ('pending', 'failed')
               OR (status = 'fetched' AND (profile_fetched_at IS NULL OR profile_fetched_at <= ?))
            ORDER BY
                CASE status WHEN 'pending' THEN 0 WHEN 'failed' THEN 1 ELSE 2 END,
                COALESCE(fetch_last_attempt_at, 0) ASC,
                pubkey_last_seen_at DESC
            LIMIT ?
            """,
            (stale_cutoff, limit * 5),
        ) as cur:
            rows = await cur.fetchall()
        selected: list[str] = []
        for row in rows:
            pubkey = str(row["pubkey"])
            last_attempt = row["fetch_last_attempt_at"]
            retry_count = int(row["retry_count"] or 0)
            if _can_attempt_identity(now_ts, last_attempt, retry_count):
                selected.append(pubkey)
            if len(selected) >= limit:
                break
        return selected

    async def update_identity_profile(
        self, pubkey: str, metadata: dict[str, str | None], *, fetched_at: int
    ) -> None:
        conn = self._conn_required()
        await conn.execute(
            """
            UPDATE identities
            SET status = 'fetched',
                name = ?,
                display_name = ?,
                about = ?,
                picture = ?,
                shape = ?,
                banner = ?,
                website = ?,
                nip05 = ?,
                lud06 = ?,
                lud16 = ?,
                profile_raw_json = ?,
                profile_fetched_at = ?,
                fetch_last_attempt_at = ?,
                retry_count = 0
            WHERE pubkey = ?
            """,
            (
                metadata.get("name"),
                metadata.get("display_name"),
                metadata.get("about"),
                metadata.get("picture"),
                metadata.get("shape"),
                metadata.get("banner"),
                metadata.get("website"),
                metadata.get("nip05"),
                metadata.get("lud06"),
                metadata.get("lud16"),
                metadata.get("profile_raw_json"),
                fetched_at,
                fetched_at,
                pubkey,
            ),
        )
        await conn.commit()

    async def mark_identity_fetch_miss(self, pubkey: str, *, attempted_at: int) -> None:
        conn = self._conn_required()
        await conn.execute(
            """
            UPDATE identities
            SET status = 'failed',
                fetch_last_attempt_at = ?,
                retry_count = retry_count + 1
            WHERE pubkey = ?
            """,
            (attempted_at, pubkey),
        )
        await conn.commit()

    async def get_identities_by_pubkeys(
        self, pubkeys: list[str]
    ) -> dict[str, dict[str, object | None]]:
        """Return identities keyed by pubkey for the provided pubkeys."""
        if not pubkeys:
            return {}
        conn = self._conn_required()
        unique_pubkeys = list(dict.fromkeys(pubkeys))
        placeholders = ", ".join(["?"] * len(unique_pubkeys))
        columns = ", ".join(_IDENTITY_COLUMNS)
        async with conn.execute(
            f"SELECT {columns} FROM identities WHERE pubkey IN ({placeholders})",
            unique_pubkeys,
        ) as cur:
            rows = await cur.fetchall()
        return {str(row["pubkey"]): {col: row[col] for col in _IDENTITY_COLUMNS} for row in rows}

    async def list_designs(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        order: str = "latest_published_at_desc",
        name_contains: str | None = None,
        creator_pubkey: str | None = None,
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
        if creator_pubkey is not None and creator_pubkey.strip():
            where += " AND pubkey = ?"
            params.append(creator_pubkey.strip().lower())
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

    async def get_counts(
        self,
        *,
        creator_pubkey: str | None = None,
    ) -> tuple[int, int]:
        """Return (designs_count, versions_count) for stats.

        If creator_pubkey is provided, both counts are scoped to that creator.
        """
        conn = self._conn_required()
        if creator_pubkey is not None and creator_pubkey.strip():
            pubkey = creator_pubkey.strip().lower()
            async with conn.execute(
                "SELECT COUNT(*) FROM designs WHERE pubkey = ?",
                (pubkey,),
            ) as cur:
                (designs_count,) = await cur.fetchone()
            async with conn.execute(
                """
                SELECT COUNT(*) FROM design_versions
                WHERE pubkey = ?
                """,
                (pubkey,),
            ) as cur:
                (versions_count,) = await cur.fetchone()
        else:
            async with conn.execute("SELECT COUNT(*) FROM designs") as cur:
                (designs_count,) = await cur.fetchone()
            async with conn.execute("SELECT COUNT(*) FROM design_versions") as cur:
                (versions_count,) = await cur.fetchone()
        return designs_count, versions_count


def _can_attempt_identity(now_ts: int, last_attempt_at: int | None, retry_count: int) -> bool:
    if last_attempt_at is None:
        return True
    if retry_count <= 0:
        return True
    retry_exp = min(retry_count, 20)
    delay_s = min(30 * (2**retry_exp), 6 * 60 * 60)
    return now_ts >= (int(last_attempt_at) + delay_s)
