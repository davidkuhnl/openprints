from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from openprints.common.design_id import is_valid_openprints_design_id
from openprints.common.event_utils import tag_values

from .store import DesignCurrentRow, DesignVersionRow, IndexStore, LogOnlyIndexStore
from .types import IngestEnvelope

logger = logging.getLogger(__name__)


@dataclass
class ReducerStats:
    processed: int = 0
    duplicates: int = 0
    reduced: int = 0


class ReducerWorker:
    def __init__(self, store: IndexStore | None = None) -> None:
        self._store = store or LogOnlyIndexStore()
        self.stats = ReducerStats()
        self._seen_event_ids: set[str] = set()
        self._current_by_design: dict[tuple[str, str], DesignCurrentRow] = {}

    async def reduce_one(self, envelope: IngestEnvelope) -> None:
        self.stats.processed += 1
        event = envelope.event

        event_id = event.get("id")
        pubkey = event.get("pubkey")
        if not isinstance(event_id, str) or not isinstance(pubkey, str):
            raise RuntimeError("Reducer invariant violated: id and pubkey must be strings")

        if event_id in self._seen_event_ids:
            self.stats.duplicates += 1
            return

        tags = event.get("tags")
        design_id = _single_tag_value(tags, "d", event_id, envelope.relay)
        if design_id is None or not is_valid_openprints_design_id(design_id):
            raise RuntimeError(
                "Reducer invariant violated: design_id must be a valid openprints:uuid-v4"
            )

        kind = event.get("kind")
        created_at = event.get("created_at")
        if not isinstance(kind, int) or not isinstance(created_at, int):
            raise RuntimeError("Reducer invariant violated: kind and created_at must be integers")

        version_row = DesignVersionRow(
            event_id=event_id,
            pubkey=pubkey,
            design_id=design_id,
            kind=kind,
            created_at=created_at,
            name=_single_tag_value(tags, "name", event_id, envelope.relay),
            format=_single_tag_value(tags, "format", event_id, envelope.relay),
            sha256=_single_tag_value(tags, "sha256", event_id, envelope.relay),
            url=_single_tag_value(tags, "url", event_id, envelope.relay),
            content=event.get("content") if isinstance(event.get("content"), str) else None,
            raw_event_json=json.dumps(event, separators=(",", ":"), ensure_ascii=False),
            received_at=envelope.received_at,
        )
        await self._store.upsert_design_version(version_row)

        self._seen_event_ids.add(event_id)
        key = (pubkey, design_id)
        current = self._current_by_design.get(key)
        if current is None:
            next_current = DesignCurrentRow(
                pubkey=pubkey,
                design_id=design_id,
                latest_event_id=event_id,
                latest_published_at=created_at,
                first_published_at=created_at,
                first_seen_at=envelope.received_at,
                updated_at=envelope.received_at,
                version_count=1,
                name=version_row.name,
                format=version_row.format,
                sha256=version_row.sha256,
                url=version_row.url,
                content=version_row.content,
                tags_json=_optional_tags_json(tags),
            )
        else:
            is_newer = _is_newer_event(
                candidate_created_at=created_at,
                candidate_event_id=event_id,
                current_created_at=current.latest_published_at,
                current_event_id=current.latest_event_id,
            )
            next_current = DesignCurrentRow(
                pubkey=pubkey,
                design_id=design_id,
                latest_event_id=event_id if is_newer else current.latest_event_id,
                latest_published_at=created_at if is_newer else current.latest_published_at,
                first_published_at=current.first_published_at,
                first_seen_at=current.first_seen_at,
                updated_at=envelope.received_at,
                version_count=current.version_count + 1,
                name=version_row.name if is_newer else current.name,
                format=version_row.format if is_newer else current.format,
                sha256=version_row.sha256 if is_newer else current.sha256,
                url=version_row.url if is_newer else current.url,
                content=version_row.content if is_newer else current.content,
                tags_json=_optional_tags_json(tags) if is_newer else current.tags_json,
            )

        self._current_by_design[key] = next_current
        await self._store.upsert_design_current(next_current)
        self.stats.reduced += 1
        logger.debug(
            "reducer_event_applied",
            extra={
                "relay": envelope.relay,
                "pubkey": pubkey,
                "design_id": design_id,
                "event_id": event_id,
                "version_count": next_current.version_count,
            },
        )


def _single_tag_value(tags: object, key: str, event_id: str, relay: str) -> str | None:
    """First tag value for key; log warning if duplicate same value, error if different."""
    values = tag_values(tags, key)
    if not values:
        return None
    if len(values) > 1:
        if len(set(values)) == 1:
            logger.warning(
                "duplicate_tag_same_value",
                extra={
                    "relay": relay,
                    "event_id": event_id,
                    "tag_key": key,
                    "value": values[0],
                },
            )
        else:
            logger.error(
                "duplicate_tag_different_values",
                extra={
                    "relay": relay,
                    "event_id": event_id,
                    "tag_key": key,
                    "values": values,
                },
            )
    return values[0]


def _optional_tags_json(tags: object) -> str:
    if not isinstance(tags, list):
        return "{}"

    required = {"d", "name", "format", "sha256", "url"}
    optional: dict[str, list[str]] = {}
    for tag in tags:
        if not (isinstance(tag, list) and len(tag) >= 2):
            continue
        if not (isinstance(tag[0], str) and isinstance(tag[1], str)):
            continue
        tag_key, tag_value = tag[0], tag[1]
        if tag_key in required:
            continue
        optional.setdefault(tag_key, []).append(tag_value)

    return json.dumps(optional, separators=(",", ":"), ensure_ascii=False)


def _is_newer_event(
    *,
    candidate_created_at: int,
    candidate_event_id: str,
    current_created_at: int,
    current_event_id: str,
) -> bool:
    if candidate_created_at > current_created_at:
        return True
    if candidate_created_at < current_created_at:
        return False
    return candidate_event_id > current_event_id
