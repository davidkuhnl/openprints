"""Identity payload serialization helpers for API responses."""

from __future__ import annotations

from openprints.api.schemas import IdentityPayload
from openprints.common.identity_utils import (
    identity_api_id_from_pubkey,
    non_empty_string,
    to_npub,
    truncate_middle,
)


def build_identity_payload(
    pubkey: str, identity: dict[str, object | None] | None
) -> IdentityPayload:
    """Build API identity payload with normalized display-name fallback."""
    npub = to_npub(pubkey)
    display_name = non_empty_string(identity.get("display_name")) if identity else None
    name = non_empty_string(identity.get("name")) if identity else None
    nip05 = non_empty_string(identity.get("nip05")) if identity else None
    display_name_resolved = display_name or name or nip05
    if display_name_resolved is None and npub is not None:
        display_name_resolved = truncate_middle(npub)

    return IdentityPayload(
        id=identity_api_id_from_pubkey(pubkey),
        pubkey=pubkey,
        status=(identity.get("status") if identity else None),
        pubkey_first_seen_at=(identity.get("pubkey_first_seen_at") if identity else None),
        pubkey_last_seen_at=(identity.get("pubkey_last_seen_at") if identity else None),
        name=(identity.get("name") if identity else None),
        display_name=(identity.get("display_name") if identity else None),
        about=(identity.get("about") if identity else None),
        picture=(identity.get("picture") if identity else None),
        banner=(identity.get("banner") if identity else None),
        website=(identity.get("website") if identity else None),
        nip05=(identity.get("nip05") if identity else None),
        lud06=(identity.get("lud06") if identity else None),
        lud16=(identity.get("lud16") if identity else None),
        profile_raw_json=(identity.get("profile_raw_json") if identity else None),
        profile_fetched_at=(identity.get("profile_fetched_at") if identity else None),
        fetch_last_attempt_at=(identity.get("fetch_last_attempt_at") if identity else None),
        retry_count=(identity.get("retry_count") if identity else None),
        npub=npub,
        display_name_resolved=display_name_resolved,
    )
