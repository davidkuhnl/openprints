"""Design list and get-by-id endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from openprints.api.deps import get_store
from openprints.common.design_id import api_id_decode, api_id_encode

router = APIRouter(prefix="/designs", tags=["designs"])


def _row_to_item(row):
    """Turn DesignCurrentRow into API response dict with id."""
    return {
        "id": api_id_encode(row.pubkey, row.design_id),
        "pubkey": row.pubkey,
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
    return {
        "items": [_row_to_item(r) for r in rows],
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
    return _row_to_item(row)
