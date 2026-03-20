"""Design payload serialization helpers for API responses."""

from __future__ import annotations

import json

from openprints.api.schemas import DesignItemPayload, DesignVersionItemPayload, IdentityPayload
from openprints.common.design_id import api_id_encode
from openprints.indexer.store import DesignCurrentRow, DesignVersionRow


def design_row_to_item(
    row: DesignCurrentRow, creator_identity: IdentityPayload
) -> DesignItemPayload:
    """Convert a design row into the API response shape."""
    return DesignItemPayload(
        id=api_id_encode(row.pubkey, row.design_id),
        pubkey=row.pubkey,
        creator_identity=creator_identity,
        design_id=row.design_id,
        latest_event_id=row.latest_event_id,
        latest_published_at=row.latest_published_at,
        first_published_at=row.first_published_at,
        first_seen_at=row.first_seen_at,
        updated_at=row.updated_at,
        version_count=row.version_count,
        name=row.name,
        format=row.format,
        sha256=row.sha256,
        url=row.url,
        content=row.content,
        tags_json=row.tags_json,
    )


def _extract_tags_json(raw_event_json: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw_event_json)
    except json.JSONDecodeError:
        return {}

    if not isinstance(parsed, dict):
        return {}

    tags = parsed.get("tags")
    if not isinstance(tags, list):
        return {}

    tag_map: dict[str, object] = {}
    for entry in tags:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        key = entry[0]
        value = entry[1]
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        current = tag_map.get(key)
        if current is None:
            tag_map[key] = value
        elif isinstance(current, list):
            current.append(value)
        else:
            tag_map[key] = [current, value]
    return tag_map


def design_version_row_to_item(row: DesignVersionRow) -> DesignVersionItemPayload:
    return DesignVersionItemPayload(
        event_id=row.event_id,
        pubkey=row.pubkey,
        design_id=row.design_id,
        previous_version_event_id=row.previous_version_event_id,
        kind=row.kind,
        created_at=row.created_at,
        received_at=row.received_at,
        name=row.name,
        format=row.format,
        sha256=row.sha256,
        url=row.url,
        content=row.content,
        tags_json=_extract_tags_json(row.raw_event_json),
        raw_event_json=row.raw_event_json,
    )
