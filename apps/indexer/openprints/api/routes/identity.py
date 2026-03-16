"""Identity get-by-id endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from openprints.api.deps import get_store
from openprints.api.schemas import IdentityPayload
from openprints.api.serializers.identity import build_identity_payload
from openprints.common.identity_utils import identity_api_id_to_pubkey

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/{identity_api_id}", response_model=IdentityPayload)
async def get_identity(identity_api_id: str) -> IdentityPayload:
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

    return build_identity_payload(pubkey, identity)
