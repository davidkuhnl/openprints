from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DesignVersionRow:
    event_id: str
    pubkey: str
    design_id: str
    previous_version_event_id: str | None
    kind: int
    created_at: int
    name: str | None
    format: str | None
    sha256: str | None
    url: str | None
    content: str | None
    raw_event_json: str
    received_at: int


@dataclass(frozen=True)
class DesignCurrentRow:
    pubkey: str
    design_id: str
    latest_event_id: str
    latest_published_at: int
    first_published_at: int
    first_seen_at: int
    updated_at: int
    version_count: int
    name: str | None
    format: str | None
    sha256: str | None
    url: str | None
    content: str | None
    tags_json: str


class IndexStore(Protocol):
    """Protocol for indexer storage backends (log-only, SQLite, etc.)."""

    async def append_design_version(self, row: DesignVersionRow) -> bool: ...

    async def upsert_design_current(self, row: DesignCurrentRow) -> None: ...

    async def get_design(self, pubkey: str, design_id: str) -> DesignCurrentRow | None: ...
    async def list_design_versions(
        self, pubkey: str, design_id: str, *, limit: int, offset: int
    ) -> tuple[list[DesignVersionRow], int]: ...

    async def ensure_identity_pending(self, pubkey: str, first_seen_at: int) -> None: ...


class LogOnlyIndexStore:
    """Store that only logs upserts; no persistence. For dev/testing."""

    async def append_design_version(self, row: DesignVersionRow) -> bool:
        logger.info(
            "append_design_version",
            extra={
                "event_id": row.event_id,
                "design_id": row.design_id,
                "pubkey": row.pubkey,
                "kind": row.kind,
                "received_at": row.received_at,
            },
        )
        return True

    async def upsert_design_current(self, row: DesignCurrentRow) -> None:
        logger.info(
            "upsert_design_current",
            extra={
                "pubkey": row.pubkey,
                "design_id": row.design_id,
                "latest_event_id": row.latest_event_id,
                "version_count": row.version_count,
            },
        )

    async def get_design(self, pubkey: str, design_id: str) -> DesignCurrentRow | None:
        logger.info(
            "get_design_log_only_store",
            extra={"pubkey": pubkey, "design_id": design_id},
        )
        return None

    async def list_design_versions(
        self, pubkey: str, design_id: str, *, limit: int, offset: int
    ) -> tuple[list[DesignVersionRow], int]:
        logger.info(
            "list_design_versions_log_only_store",
            extra={"pubkey": pubkey, "design_id": design_id, "limit": limit, "offset": offset},
        )
        return [], 0

    async def ensure_identity_pending(self, pubkey: str, first_seen_at: int) -> None:
        logger.info(
            "ensure_identity_pending",
            extra={"pubkey": pubkey, "first_seen_at": first_seen_at},
        )

    async def list_identity_pubkeys_for_refresh(
        self, *, limit: int, stale_after_s: int, now_ts: int
    ) -> list[str]:
        logger.info(
            "list_identity_pubkeys_for_refresh",
            extra={"limit": limit, "stale_after_s": stale_after_s, "now_ts": now_ts},
        )
        return []

    async def update_identity_profile(
        self, pubkey: str, metadata: dict[str, str | None], *, fetched_at: int
    ) -> None:
        logger.info(
            "update_identity_profile",
            extra={"pubkey": pubkey, "fetched_at": fetched_at},
        )

    async def mark_identity_fetch_miss(self, pubkey: str, *, attempted_at: int) -> None:
        logger.info(
            "mark_identity_fetch_miss",
            extra={"pubkey": pubkey, "attempted_at": attempted_at},
        )
