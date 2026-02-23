"""Design id: protocol (openprints:uuid-v4) and API composite id (URL-safe encode/decode)."""

from __future__ import annotations

import base64
from uuid import UUID, uuid4

from openprints.common.errors import invalid_value


def is_valid_openprints_design_id(value: str) -> bool:
    """Return True if value is an openprints design id (openprints:uuid or bare uuid-v4)."""
    if not value or not isinstance(value, str):
        return False
    candidate = value[len("openprints:") :] if value.startswith("openprints:") else value
    try:
        parsed = UUID(candidate)
    except (ValueError, TypeError):
        return False
    return parsed.version == 4


def normalize_design_id(raw: str | None) -> tuple[str | None, bool, list[dict[str, str]]]:
    """Normalize design id for the d tag: None or uuid/openprints:uuid -> openprints:uuid-v4.

    Returns (canonical_str, was_generated, errors). If raw is None, generates a new uuid4.
    """
    generated = raw is None
    candidate = raw or str(uuid4())
    if candidate.startswith("openprints:"):
        candidate = candidate[len("openprints:") :]

    try:
        parsed = UUID(candidate)
    except (ValueError, TypeError):
        return None, generated, [invalid_value("design_id", "design_id must be a valid UUID")]

    if parsed.version != 4:
        return None, generated, [invalid_value("design_id", "design_id must be a UUID version 4")]

    return f"openprints:{parsed}", generated, []


# --- API composite id (pubkey + design_id) for GET /designs/{id} ---


def api_id_encode(pubkey: str, design_id: str) -> str:
    """Encode (pubkey, design_id) to a URL-safe opaque id for GET /designs/{id}."""
    raw = f"{pubkey}\n{design_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def api_id_decode(api_id: str) -> tuple[str, str] | None:
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
