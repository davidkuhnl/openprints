"""Openprints design id: openprints:uuid-v4, shared by build and indexer."""

from __future__ import annotations

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
