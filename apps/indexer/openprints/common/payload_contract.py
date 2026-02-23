from __future__ import annotations

from typing import Any

from openprints.common.error_codes import (
    DRAFT_CONTAINS_SIGNED_FIELDS,
    SIGNED_MISSING_SIGNATURE_FIELDS,
    UNSUPPORTED_ARTIFACT_VERSION,
    UNSUPPORTED_EVENT_KIND,
)
from openprints.common.errors import (
    invalid_type,
    invalid_value,
    make_error,
    missing_required_field,
    missing_required_tag,
)

ARTIFACT_VERSION = 1
SUPPORTED_ARTIFACT_VERSIONS = {ARTIFACT_VERSION}
SUPPORTED_EVENT_KIND = 33301


def _is_tag_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    for tag in value:
        if not isinstance(tag, list):
            return False
        if not all(isinstance(part, str) for part in tag):
            return False
    return True


def _collect_tag_values(tags: list[list[str]], key: str) -> list[str]:
    return [tag[1] for tag in tags if len(tag) >= 2 and tag[0] == key]


def validate_payload(payload: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    if not isinstance(payload, dict):
        return [invalid_type("$", "an object")]

    artifact_version = payload.get("artifact_version")
    if artifact_version is None:
        errors.append(missing_required_field("artifact_version"))
    elif not isinstance(artifact_version, int):
        errors.append(invalid_type("artifact_version", "an integer"))
    elif artifact_version not in SUPPORTED_ARTIFACT_VERSIONS:
        errors.append(
            make_error(
                UNSUPPORTED_ARTIFACT_VERSION,
                "artifact_version",
                f"artifact_version {artifact_version} is not supported",
            )
        )

    event = payload.get("event")
    if event is None:
        errors.append(missing_required_field("event"))
        return errors
    if not isinstance(event, dict):
        errors.append(invalid_type("event", "an object"))
        return errors

    meta = payload.get("meta")
    if meta is None:
        errors.append(missing_required_field("meta"))
        return errors
    if not isinstance(meta, dict):
        errors.append(invalid_type("meta", "an object"))
        return errors

    state = meta.get("state")
    if state is None:
        errors.append(missing_required_field("meta.state"))
    elif state not in {"draft", "signed"}:
        errors.append(
            invalid_value(
                "meta.state",
                "meta.state must be one of: draft, signed",
            )
        )

    source = meta.get("source")
    if source is None:
        errors.append(missing_required_field("meta.source"))
    elif not isinstance(source, str) or not source.strip():
        errors.append(invalid_value("meta.source", "meta.source must be a non-empty string"))

    for field in ("kind", "created_at", "tags", "content"):
        if field not in event:
            errors.append(missing_required_field(f"event.{field}"))

    kind = event.get("kind")
    if kind is not None:
        if not isinstance(kind, int):
            errors.append(invalid_type("event.kind", "an integer"))
        elif kind != SUPPORTED_EVENT_KIND:
            errors.append(
                make_error(
                    UNSUPPORTED_EVENT_KIND,
                    "event.kind",
                    f"event.kind must be {SUPPORTED_EVENT_KIND}",
                )
            )

    created_at = event.get("created_at")
    if created_at is not None and not isinstance(created_at, int):
        errors.append(invalid_type("event.created_at", "an integer"))

    tags = event.get("tags")
    if tags is not None and not _is_tag_list(tags):
        errors.append(invalid_type("event.tags", "a list of string lists"))

    content = event.get("content")
    if content is not None and not isinstance(content, str):
        errors.append(invalid_type("event.content", "a string"))

    if isinstance(tags, list) and _is_tag_list(tags):
        required_tags = ("d", "name", "format", "sha256", "url")
        for tag_name in required_tags:
            if not any(len(tag) >= 2 and tag[0] == tag_name for tag in tags):
                errors.append(missing_required_tag(tag_name))

        name_values = _collect_tag_values(tags, "name")
        if name_values:
            normalized_name = " ".join(name_values[0].strip().split())
            if not (1 <= len(normalized_name) <= 120):
                errors.append(
                    invalid_value(
                        "event.tags[name]",
                        "name must be 1..120 characters after trimming/whitespace normalization",
                    )
                )

    if state == "draft":
        forbidden_in_draft = ("id", "sig")
        for field in forbidden_in_draft:
            if field in event:
                errors.append(
                    make_error(
                        DRAFT_CONTAINS_SIGNED_FIELDS,
                        f"event.{field}",
                        f"event.{field} must not be present when meta.state=draft",
                    )
                )
    elif state == "signed":
        for field in ("id", "sig", "pubkey"):
            if field not in event:
                errors.append(
                    make_error(
                        SIGNED_MISSING_SIGNATURE_FIELDS,
                        f"event.{field}",
                        f"event.{field} is required when meta.state=signed",
                    )
                )

    return errors
