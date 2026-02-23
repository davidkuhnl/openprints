"""Encode/decode design composite id for API (pubkey + design_id)."""

from __future__ import annotations

import base64


def design_id_encode(pubkey: str, design_id: str) -> str:
    """Encode (pubkey, design_id) to a URL-safe opaque id for GET /designs/{id}."""
    raw = f"{pubkey}\n{design_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def design_id_decode(api_id: str) -> tuple[str, str] | None:
    """Decode API id to (pubkey, design_id). Returns None if invalid."""
    try:
        padding = 4 - (len(api_id) % 4)
        if padding != 4:
            api_id += "=" * padding
        raw = base64.urlsafe_b64decode(api_id.encode("ascii")).decode("utf-8")
        if "\n" not in raw:
            return None
        pubkey, design_id = raw.split("\n", 1)
        return (pubkey, design_id)
    except Exception:
        return None
