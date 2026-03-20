"""Reusable validators for Nostr events used by API and workers."""

from __future__ import annotations

import re
from typing import cast

from openprints.common.design_event_schema import (
    SCHEMA_TAG_KEY,
    UNKNOWN_SCHEMA_VERSION,
    resolve_design_event_schema_version,
)
from openprints.common.design_id import is_valid_openprints_design_id
from openprints.common.errors import (
    invalid_type,
    invalid_value,
    missing_required_field,
    missing_required_tag,
)
from openprints.common.event_types import SignedEvent
from openprints.common.event_utils import tag_values

_CONTROL_OR_BIDI_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")
_HEX_64_RE = re.compile(r"^[a-f0-9]{64}$")
_HEX_128_RE = re.compile(r"^[a-f0-9]{128}$")
_FORMAT_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]{0,31}$")


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


def _is_https_url(value: str) -> bool:
    return value.startswith("https://")


def validate_signed_design_event(
    event: object,
) -> tuple[SignedEvent | None, list[dict[str, str]]]:
    """Validate signed kind-33301 design event shape and business constraints."""
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

    d_values = tag_values(tags, "d")
    name_values = tag_values(tags, "name")
    format_values = tag_values(tags, "format")
    url_values = tag_values(tags, "url")
    sha_values = tag_values(tags, "sha256")
    previous_values = tag_values(tags, "previous")
    previous_version_event_id_values = tag_values(tags, "previous_version_event_id")

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

    schema_version = resolve_design_event_schema_version(signed_event)
    if schema_version == UNKNOWN_SCHEMA_VERSION:
        errors.append(
            invalid_value(
                f"event.tags[{SCHEMA_TAG_KEY}]",
                "openprints_schema must appear at most once and include a non-empty string value",
            )
        )

    if previous_values:
        previous_event_id = previous_values[0].lower()
        if not _HEX_64_RE.fullmatch(previous_event_id):
            errors.append(
                invalid_value(
                    "event.tags[previous]",
                    "previous must be exactly 64 lowercase hex chars",
                )
            )
        elif previous_event_id == event_id:
            errors.append(
                invalid_value(
                    "event.tags[previous]",
                    "previous cannot reference event.id",
                )
            )

    if previous_version_event_id_values:
        previous_version_event_id = previous_version_event_id_values[0].lower()
        if not _HEX_64_RE.fullmatch(previous_version_event_id):
            errors.append(
                invalid_value(
                    "event.tags[previous_version_event_id]",
                    "previous_version_event_id must be exactly 64 lowercase hex chars",
                )
            )
        elif previous_version_event_id == event_id:
            errors.append(
                invalid_value(
                    "event.tags[previous_version_event_id]",
                    "previous_version_event_id cannot reference event.id",
                )
            )

    if _CONTROL_OR_BIDI_RE.search(signed_event["content"]):
        errors.append(
            invalid_value(
                "event.content",
                "content contains unsupported control or bidi characters",
            )
        )

    return (None, errors) if errors else (signed_event, [])
