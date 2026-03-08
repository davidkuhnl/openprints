"""Design list and get-by-id endpoints."""

from __future__ import annotations

import re
from typing import cast

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from openprints.api.deps import get_ready_context, get_store
from openprints.api.services.relay_publish import publish_event_to_relays
from openprints.common.design_id import (
    api_id_decode,
    api_id_encode,
    is_valid_openprints_design_id,
)
from openprints.common.errors import (
    invalid_type,
    invalid_value,
    missing_required_field,
    missing_required_tag,
)
from openprints.common.event_types import SignedEvent
from openprints.common.event_utils import tag_values, verify_event_signature
from openprints.common.identity_utils import (
    identity_api_id_from_pubkey,
    identity_api_id_to_pubkey,
    non_empty_string,
    to_npub,
    truncate_middle,
)

router = APIRouter(prefix="/designs", tags=["designs"])

_CONTROL_OR_BIDI_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")
_HEX_64_RE = re.compile(r"^[a-f0-9]{64}$")
_HEX_128_RE = re.compile(r"^[a-f0-9]{128}$")
_FORMAT_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]{0,31}$")


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


def _collect_tag_values(tags: object, key: str) -> list[str]:
    return tag_values(tags, key)


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


def _is_https_url(value: str) -> bool:
    return value.startswith("https://")


def _validate_signed_design_event(event: object) -> tuple[SignedEvent | None, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    if not isinstance(event, dict):
        return None, [invalid_type("event", "an object")]

    required_fields = ("id", "pubkey", "created_at", "kind", "tags", "content", "sig")
    for field in required_fields:
        if field not in event:
            errors.append(missing_required_field(f"event.{field}"))

    if errors:
        return None, errors

    if not isinstance(event.get("id"), str):
        errors.append(invalid_type("event.id", "a string"))
    if not isinstance(event.get("pubkey"), str):
        errors.append(invalid_type("event.pubkey", "a string"))
    if not isinstance(event.get("created_at"), int):
        errors.append(invalid_type("event.created_at", "an integer"))
    if not isinstance(event.get("kind"), int):
        errors.append(invalid_type("event.kind", "an integer"))
    if not isinstance(event.get("tags"), list):
        errors.append(invalid_type("event.tags", "a list of tag arrays"))
    if not isinstance(event.get("content"), str):
        errors.append(invalid_type("event.content", "a string"))
    if not isinstance(event.get("sig"), str):
        errors.append(invalid_type("event.sig", "a string"))
    if errors:
        return None, errors

    signed_event = cast(SignedEvent, event)
    event_id = signed_event["id"].lower()
    pubkey = signed_event["pubkey"].lower()
    sig = signed_event["sig"].lower()

    if signed_event["kind"] != 33301:
        errors.append(invalid_value("event.kind", "event.kind must be 33301"))
    if not _HEX_64_RE.fullmatch(event_id):
        errors.append(invalid_value("event.id", "event.id must be 64-char hex"))
    if not _HEX_64_RE.fullmatch(pubkey):
        errors.append(invalid_value("event.pubkey", "event.pubkey must be 64-char hex"))
    if not _HEX_128_RE.fullmatch(sig):
        errors.append(invalid_value("event.sig", "event.sig must be 128-char hex"))
    if signed_event["created_at"] <= 0:
        errors.append(
            invalid_value(
                "event.created_at",
                "event.created_at must be greater than zero",
            )
        )

    tags = signed_event["tags"]
    if not all(
        isinstance(tag, list) and all(isinstance(part, str) for part in tag) for tag in tags
    ):
        errors.append(invalid_value("event.tags", "each tag must be an array of strings"))
        return None, errors

    d_values = _collect_tag_values(tags, "d")
    name_values = _collect_tag_values(tags, "name")
    format_values = _collect_tag_values(tags, "format")
    url_values = _collect_tag_values(tags, "url")
    sha_values = _collect_tag_values(tags, "sha256")

    if not d_values:
        errors.append(missing_required_tag("d"))
    if not name_values:
        errors.append(missing_required_tag("name"))
    if not format_values:
        errors.append(missing_required_tag("format"))
    if not url_values:
        errors.append(missing_required_tag("url"))

    if d_values and not is_valid_openprints_design_id(d_values[0]):
        errors.append(invalid_value("event.tags[d]", "d must be an openprints: UUID v4 design id"))

    if name_values:
        normalized_name = _normalize_name(name_values[0])
        if not (1 <= len(normalized_name) <= 120):
            errors.append(
                invalid_value(
                    "event.tags[name]",
                    "name must be 1..120 chars after trim and whitespace normalization",
                )
            )
        if _CONTROL_OR_BIDI_RE.search(normalized_name):
            errors.append(
                invalid_value(
                    "event.tags[name]",
                    "name contains unsupported control or bidi characters",
                )
            )

    if format_values and not _FORMAT_RE.fullmatch(format_values[0].lower()):
        errors.append(
            invalid_value(
                "event.tags[format]",
                "format must be lowercase and use only [a-z0-9+.-]",
            )
        )

    if url_values and not _is_https_url(url_values[0]):
        errors.append(invalid_value("event.tags[url]", "url must be an https URL"))

    if sha_values and not _HEX_64_RE.fullmatch(sha_values[0].lower()):
        errors.append(
            invalid_value("event.tags[sha256]", "sha256 must be exactly 64 lowercase hex chars")
        )

    if _CONTROL_OR_BIDI_RE.search(signed_event["content"]):
        errors.append(
            invalid_value(
                "event.content",
                "content contains unsupported control or bidi characters",
            )
        )

    return (None, errors) if errors else (signed_event, [])


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
            _row_to_item(r, _build_creator_identity(r.pubkey, identities_by_pubkey.get(r.pubkey)))
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
    return _row_to_item(row, _build_creator_identity(row.pubkey, identity))


@router.post("/publish")
async def publish_design(event: dict) -> JSONResponse:
    """Verify and publish a signed kind-33301 event to configured relays."""
    signed_event, event_errors = _validate_signed_design_event(event)
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
