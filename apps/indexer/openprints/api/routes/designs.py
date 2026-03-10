"""Design list and get-by-id endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from openprints.api.deps import get_ready_context, get_store
from openprints.api.serializers.designs import design_row_to_item
from openprints.api.serializers.identity import build_identity_payload
from openprints.api.services.relay_publish import publish_event_to_relays
from openprints.common.design_id import api_id_decode
from openprints.common.errors import invalid_value
from openprints.common.event_utils import verify_event_signature
from openprints.common.event_validation import validate_signed_design_event
from openprints.common.identity_utils import identity_api_id_to_pubkey

router = APIRouter(prefix="/designs", tags=["designs"])


@router.get("")
async def list_designs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query(
        "latest_published_at_desc",
        description="Sort: latest_published_at_desc|asc, first_published_at_desc|asc",
    ),
    q: str | None = Query(None, description="Search designs by name (substring)."),
    identity_id: str | None = Query(
        default=None,
        description="Filter designs by creator identity id (npub or hex pubkey).",
    ),
) -> dict:
    """List designs with pagination and optional filters."""
    creator_pubkey: str | None = None
    if identity_id is not None:
        creator_pubkey = identity_api_id_to_pubkey(identity_id)
        if creator_pubkey is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid identity id format.",
            )
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
        creator_pubkey=creator_pubkey,
    )
    identities_by_pubkey = await store.get_identities_by_pubkeys([row.pubkey for row in rows])
    return {
        "items": [
            design_row_to_item(
                r, build_identity_payload(r.pubkey, identities_by_pubkey.get(r.pubkey))
            )
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
async def design_stats(
    identity_id: str | None = Query(
        default=None,
        description="Filter stats by creator identity id (npub or hex pubkey).",
    ),
) -> dict:
    """Return total number of designs and versions, optionally scoped to a creator."""
    creator_pubkey: str | None = None
    if identity_id is not None:
        creator_pubkey = identity_api_id_to_pubkey(identity_id)
        if creator_pubkey is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid identity id format.",
            )

    store = get_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured; run indexer with database_path first.",
        )
    designs_count, versions_count = await store.get_counts(creator_pubkey=creator_pubkey)
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
    return design_row_to_item(row, build_identity_payload(row.pubkey, identity))


@router.post("/publish")
async def publish_design(event: dict) -> JSONResponse:
    """Verify and publish a signed kind-33301 event to configured relays."""
    signed_event, event_errors = validate_signed_design_event(event)
    if event_errors:
        return JSONResponse(status_code=400, content={"ok": False, "errors": event_errors})

    assert signed_event is not None
    sig_error = verify_event_signature(signed_event)
    if sig_error is not None:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "errors": [invalid_value("event", sig_error)]},
        )

    _db_path, relay_urls = get_ready_context()
    if not relay_urls:
        raise HTTPException(
            status_code=503,
            detail="No relay URLs configured. Set OPENPRINTS_RELAY_URLS or indexer.relays.",
        )

    relay_results = await publish_event_to_relays(relay_urls, signed_event, timeout_s=8.0)
    accepted = [result for result in relay_results if bool(result.get("accepted"))]
    duplicates = [result for result in accepted if bool(result.get("duplicate"))]
    rejected = [result for result in relay_results if not bool(result.get("accepted"))]

    payload = {
        "event_id": signed_event["id"],
        "relay_results": relay_results,
        "accepted_relay_count": len(accepted),
        "duplicate_relay_count": len(duplicates),
        "rejected_relay_count": len(rejected),
    }

    if accepted:
        return JSONResponse(status_code=202, content={"ok": True, **payload})

    return JSONResponse(
        status_code=502,
        content={
            "ok": False,
            "errors": [
                invalid_value(
                    "relay",
                    "Event verification passed but all relay publishes failed.",
                )
            ],
            **payload,
        },
    )
