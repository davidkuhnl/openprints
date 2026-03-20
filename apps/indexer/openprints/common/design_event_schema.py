"""Schema helpers for kind-33301 OpenPrints design events."""

from __future__ import annotations

from typing import Literal

SCHEMA_TAG_KEY = "openprints_schema"
LEGACY_SCHEMA_VERSION = "1.0"
SCHEMA_VERSION_1_1 = "1.1"
UNKNOWN_SCHEMA_VERSION = "unknown"

SchemaVersion = Literal["1.0", "1.1", "unknown"] | str


def resolve_design_event_schema_version(event: object) -> SchemaVersion:
    """Resolve schema version from event tags.

    Rules:
    - missing `openprints_schema` tag => "1.0" (legacy)
    - single well-formed `openprints_schema` tag => its value (for example "1.1")
    - malformed/ambiguous tag shape => "unknown"
    """
    if not isinstance(event, dict):
        return UNKNOWN_SCHEMA_VERSION

    tags = event.get("tags")
    if not isinstance(tags, list):
        return LEGACY_SCHEMA_VERSION

    schema_values: list[str] = []
    saw_malformed_schema_tag = False

    for tag in tags:
        if not isinstance(tag, list) or not tag:
            continue
        if not isinstance(tag[0], str) or tag[0] != SCHEMA_TAG_KEY:
            continue
        if len(tag) < 2 or not isinstance(tag[1], str):
            saw_malformed_schema_tag = True
            continue
        schema_values.append(tag[1].strip())

    if saw_malformed_schema_tag:
        return UNKNOWN_SCHEMA_VERSION
    if not schema_values:
        return LEGACY_SCHEMA_VERSION
    if len(schema_values) != 1:
        return UNKNOWN_SCHEMA_VERSION
    if not schema_values[0]:
        return UNKNOWN_SCHEMA_VERSION
    return schema_values[0]
