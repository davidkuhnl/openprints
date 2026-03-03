"""Identity get-by-id endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from openprints.api.deps import get_store
from openprints.common.identity_utils import (
    identity_api_id_from_pubkey,
    identity_api_id_to_pubkey,
    non_empty_string,
    to_npub,
    truncate_middle,
)

router = APIRouter(prefix="/identity", tags=["identity"])


def _build_identity_payload(
    pubkey: str, identity: dict[str, object | None]
) -> dict[str, object | None]:
    npub = to_npub(pubkey)
    display_name = non_empty_string(identity.get("display_name"))
    name = non_empty_string(identity.get("name"))
    nip05 = non_empty_string(identity.get("nip05"))
    display_name_resolved = display_name or name or nip05
    if display_name_resolved is None and npub is not None:
        display_name_resolved = truncate_middle(npub)

    return {
        "id": identity_api_id_from_pubkey(pubkey),
        "pubkey": pubkey,
        "status": identity.get("status"),
        "pubkey_first_seen_at": identity.get("pubkey_first_seen_at"),
        "pubkey_last_seen_at": identity.get("pubkey_last_seen_at"),
        "name": identity.get("name"),
        "display_name": identity.get("display_name"),
        "about": identity.get("about"),
        "picture": identity.get("picture"),
        "banner": identity.get("banner"),
        "website": identity.get("website"),
        "nip05": identity.get("nip05"),
        "lud06": identity.get("lud06"),
        "lud16": identity.get("lud16"),
        "profile_raw_json": identity.get("profile_raw_json"),
        "profile_fetched_at": identity.get("profile_fetched_at"),
        "fetch_last_attempt_at": identity.get("fetch_last_attempt_at"),
        "retry_count": identity.get("retry_count"),
        "npub": npub,
        "display_name_resolved": display_name_resolved,
    }


@router.get("/{identity_api_id}")
async def get_identity(identity_api_id: str) -> dict[str, object | None]:
    """Return a single identity by identity API id (npub or hex pubkey)."""
    pubkey = identity_api_id_to_pubkey(identity_api_id)
    if pubkey is None:
        raise HTTPException(status_code=400, detail="Invalid identity id format.")

    store = get_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured; run indexer with database_path first.",
        )

    identity = (await store.get_identities_by_pubkeys([pubkey])).get(pubkey)
    if identity is None:
        raise HTTPException(status_code=404, detail="Identity not found.")

    return _build_identity_payload(pubkey, identity)
