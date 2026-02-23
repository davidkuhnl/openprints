from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DesignVersionRow:
    event_id: str
    pubkey: str
    design_id: str
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


class LogOnlyIndexStore:
    """Store that only logs upserts; no persistence. For dev/testing."""

    async def upsert_design_version(self, row: DesignVersionRow) -> None:
        logger.info(
            "upsert_design_version",
            extra={
                "event_id": row.event_id,
                "design_id": row.design_id,
                "pubkey": row.pubkey,
                "kind": row.kind,
                "received_at": row.received_at,
            },
        )

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
