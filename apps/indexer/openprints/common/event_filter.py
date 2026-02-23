"""Filter for Nostr events that are ingestible as design events."""

from __future__ import annotations

from openprints.common.design_id import is_valid_openprints_design_id
from openprints.common.event_utils import tag_value


def is_ingestible_design_event(event: dict) -> bool:
    """Return True if the event is ingestible (id, pubkey, kind, created_at, openprints d tag).

    Duplicate detection is not done here; the reducer handles that.
    """
    if not isinstance(event.get("id"), str) or not isinstance(event.get("pubkey"), str):
        return False
    d_value = tag_value(event.get("tags"), "d")
    if d_value is None or not is_valid_openprints_design_id(d_value):
        return False
    if not isinstance(event.get("kind"), int) or not isinstance(event.get("created_at"), int):
        return False
    return True
