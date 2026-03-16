"""Design list and get-by-id endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from openprints.api.deps import get_ready_context, get_store
from openprints.api.schemas import (
    ApiError,
    DesignItemPayload,
    DesignListResponse,
    DesignStatsResponse,
    PublishDesignResponse,
    PublishRelayResult,
    SignedDesignEvent,
)
from openprints.api.serializers.designs import design_row_to_item
from openprints.api.serializers.identity import build_identity_payload
from openprints.api.services.relay_publish import publish_event_to_relays
from openprints.common.design_id import api_id_decode
from openprints.common.errors import invalid_value
from openprints.common.event_utils import verify_event_signature
from openprints.common.event_validation import validate_signed_design_event
from openprints.common.identity_utils import identity_api_id_to_pubkey

router = APIRouter(prefix="/designs", tags=["designs"])


@router.get("", response_model=DesignListResponse)
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
) -> DesignListResponse:
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
    items: list[DesignItemPayload] = [
        design_row_to_item(r, build_identity_payload(r.pubkey, identities_by_pubkey.get(r.pubkey)))
        for r in rows
    ]
    return DesignListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/stats", response_model=DesignStatsResponse)
async def design_stats(
    identity_id: str | None = Query(
        default=None,
        description="Filter stats by creator identity id (npub or hex pubkey).",
    ),
) -> DesignStatsResponse:
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
    return DesignStatsResponse(designs=designs_count, versions=versions_count)


@router.get("/{design_api_id}", response_model=DesignItemPayload)
async def get_design(design_api_id: str) -> DesignItemPayload:
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


@router.post(
    "/publish",
    response_model=PublishDesignResponse,
    status_code=202,
    responses={
        400: {"model": PublishDesignResponse},
        502: {"model": PublishDesignResponse},
    },
)
async def publish_design(event: SignedDesignEvent) -> JSONResponse:
    """Verify and publish a signed kind-33301 event to configured relays."""
    signed_event, event_errors = validate_signed_design_event(event.model_dump())
    if event_errors:
        error_payload = PublishDesignResponse(
            ok=False,
            errors=[ApiError(path=err["path"], message=err["message"]) for err in event_errors],
        )
        return JSONResponse(status_code=400, content=error_payload.model_dump())

    assert signed_event is not None
    sig_error = verify_event_signature(signed_event)
    if sig_error is not None:
        signature_error = invalid_value("event", sig_error)
        error_payload = PublishDesignResponse(
            ok=False,
            errors=[
                ApiError(
                    path=signature_error["path"],
                    message=signature_error["message"],
                )
            ],
        )
        return JSONResponse(
            status_code=400,
            content=error_payload.model_dump(),
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

    payload = PublishDesignResponse(
        ok=bool(accepted),
        event_id=signed_event["id"],
        relay_results=[
            PublishRelayResult(
                relay=str(result.get("relay") or ""),
                event_id=str(result.get("event_id") or signed_event["id"]),
                accepted=bool(result.get("accepted")),
                duplicate=bool(result.get("duplicate")),
                message=str(result.get("message") or ""),
            )
            for result in relay_results
        ],
        accepted_relay_count=len(accepted),
        duplicate_relay_count=len(duplicates),
        rejected_relay_count=len(rejected),
    )

    if accepted:
        return JSONResponse(status_code=202, content=payload.model_dump())

    all_failed_error = invalid_value(
        "relay",
        "Event verification passed but all relay publishes failed.",
    )
    failed_payload = payload.model_copy(
        update={
            "ok": False,
            "errors": [
                ApiError(
                    path=all_failed_error["path"],
                    message=all_failed_error["message"],
                )
            ],
        }
    )
    return JSONResponse(
        status_code=502,
        content=failed_payload.model_dump(),
    )
