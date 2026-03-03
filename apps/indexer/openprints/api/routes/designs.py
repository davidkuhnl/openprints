"""Design list and get-by-id endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from openprints.api.deps import get_store
from openprints.common.design_id import api_id_decode, api_id_encode
from openprints.common.identity_utils import (
    identity_api_id_from_pubkey,
    non_empty_string,
    to_npub,
    truncate_middle,
)

router = APIRouter(prefix="/designs", tags=["designs"])


def _build_creator_identity(
    pubkey: str, identity: dict[str, object | None] | None
) -> dict[str, object | None]:
    npub = to_npub(pubkey)
    display_name = non_empty_string(identity.get("display_name")) if identity else None
    name = non_empty_string(identity.get("name")) if identity else None
    nip05 = non_empty_string(identity.get("nip05")) if identity else None
    display_name_resolved = display_name or name or nip05
    if display_name_resolved is None and npub is not None:
        display_name_resolved = truncate_middle(npub)
    return {
        "id": identity_api_id_from_pubkey(pubkey),
        "pubkey": pubkey,
        "status": identity.get("status") if identity else None,
        "pubkey_first_seen_at": identity.get("pubkey_first_seen_at") if identity else None,
        "pubkey_last_seen_at": identity.get("pubkey_last_seen_at") if identity else None,
        "name": identity.get("name") if identity else None,
        "display_name": identity.get("display_name") if identity else None,
        "about": identity.get("about") if identity else None,
        "picture": identity.get("picture") if identity else None,
        "banner": identity.get("banner") if identity else None,
        "website": identity.get("website") if identity else None,
        "nip05": identity.get("nip05") if identity else None,
        "lud06": identity.get("lud06") if identity else None,
        "lud16": identity.get("lud16") if identity else None,
        "profile_raw_json": identity.get("profile_raw_json") if identity else None,
        "profile_fetched_at": identity.get("profile_fetched_at") if identity else None,
        "fetch_last_attempt_at": identity.get("fetch_last_attempt_at") if identity else None,
        "retry_count": identity.get("retry_count") if identity else None,
        "npub": npub,
        "display_name_resolved": display_name_resolved,
    }


def _row_to_item(row, creator_identity: dict[str, object | None]):
    """Turn DesignCurrentRow into API response dict with id."""
    return {
        "id": api_id_encode(row.pubkey, row.design_id),
        "pubkey": row.pubkey,
        "creator_identity": creator_identity,
        "design_id": row.design_id,
        "latest_event_id": row.latest_event_id,
        "latest_published_at": row.latest_published_at,
        "first_published_at": row.first_published_at,
        "first_seen_at": row.first_seen_at,
        "updated_at": row.updated_at,
        "version_count": row.version_count,
        "name": row.name,
        "format": row.format,
        "sha256": row.sha256,
        "url": row.url,
        "content": row.content,
        "tags_json": row.tags_json,
    }


@router.get("")
async def list_designs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query(
        "latest_published_at_desc",
        description="Sort: latest_published_at_desc|asc, first_published_at_desc|asc",
    ),
    q: str | None = Query(None, description="Search designs by name (substring)."),
) -> dict:
    """List designs with pagination and optional name search."""
    store = get_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured; run indexer with database_path first.",
        )
    if order not in (
        "latest_published_at_desc",
        "latest_published_at_asc",
        "first_published_at_desc",
        "first_published_at_asc",
    ):
        order = "latest_published_at_desc"
    rows, total = await store.list_designs(
        limit=limit,
        offset=offset,
        order=order,
        name_contains=q.strip() if q else None,
    )
    identities_by_pubkey = await store.get_identities_by_pubkeys([row.pubkey for row in rows])
    return {
        "items": [
            _row_to_item(r, _build_creator_identity(r.pubkey, identities_by_pubkey.get(r.pubkey)))
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
async def design_stats() -> dict:
    """Return total number of designs and versions."""
    store = get_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured; run indexer with database_path first.",
        )
    designs_count, versions_count = await store.get_counts()
    return {"designs": designs_count, "versions": versions_count}


@router.get("/{design_api_id}")
async def get_design(design_api_id: str) -> dict:
    """Return a single design by its API id (opaque id from list designs)."""
    pair = api_id_decode(design_api_id)
    if pair is None:
        raise HTTPException(status_code=400, detail="Invalid design id format.")
    store = get_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured; run indexer with database_path first.",
        )
    pubkey, design_id = pair
    row = await store.get_design(pubkey, design_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Design not found.")
    identity = (await store.get_identities_by_pubkeys([row.pubkey])).get(row.pubkey)
    return _row_to_item(row, _build_creator_identity(row.pubkey, identity))
