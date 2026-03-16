"""Design payload serialization helpers for API responses."""

from __future__ import annotations

from openprints.api.schemas import DesignItemPayload, IdentityPayload
from openprints.common.design_id import api_id_encode
from openprints.indexer.store import DesignCurrentRow


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
