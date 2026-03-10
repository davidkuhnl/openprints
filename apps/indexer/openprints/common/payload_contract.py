from __future__ import annotations

import json
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
from openprints.common.event_utils import tag_values

ARTIFACT_VERSION = 1
SUPPORTED_ARTIFACT_VERSIONS = {ARTIFACT_VERSION}
SUPPORTED_EVENT_TYPES = {"design", "identity"}
SUPPORTED_KIND_BY_EVENT_TYPE = {
    "design": 33301,
    "identity": 0,
}


def _is_tag_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    for tag in value:
        if not isinstance(tag, list):
            return False
        if not all(isinstance(part, str) for part in tag):
            return False
    return True


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

    event_type = meta.get("event_type")
    if event_type is None:
        errors.append(missing_required_field("meta.event_type"))
    elif not isinstance(event_type, str):
        errors.append(invalid_type("meta.event_type", "a string"))
        event_type = None
    elif event_type not in SUPPORTED_EVENT_TYPES:
        errors.append(
            invalid_value(
                "meta.event_type",
                f"meta.event_type must be one of: {', '.join(sorted(SUPPORTED_EVENT_TYPES))}",
            )
        )

    for field in ("kind", "created_at", "tags", "content"):
        if field not in event:
            errors.append(missing_required_field(f"event.{field}"))

    kind = event.get("kind")
    if kind is not None:
        if not isinstance(kind, int):
            errors.append(invalid_type("event.kind", "an integer"))
        elif (
            isinstance(event_type, str)
            and event_type in SUPPORTED_KIND_BY_EVENT_TYPE
            and kind != SUPPORTED_KIND_BY_EVENT_TYPE[event_type]
        ):
            errors.append(
                make_error(
                    UNSUPPORTED_EVENT_KIND,
                    "event.kind",
                    "event.kind must be "
                    f"{SUPPORTED_KIND_BY_EVENT_TYPE[event_type]} for event_type '{event_type}'",
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
        if event_type == "design":
            required_tags = ("d", "name", "format", "sha256", "url")
            for tag_name in required_tags:
                if not any(len(tag) >= 2 and tag[0] == tag_name for tag in tags):
                    errors.append(missing_required_tag(tag_name))

            name_values = tag_values(tags, "name")
            if name_values:
                normalized_name = " ".join(name_values[0].strip().split())
                if not (1 <= len(normalized_name) <= 120):
                    errors.append(
                        invalid_value(
                            "event.tags[name]",
                            "name must be 1..120 characters after trimming/whitespace "
                            "normalization",
                        )
                    )
        elif event_type == "identity":
            if isinstance(content, str):
                try:
                    parsed_content = json.loads(content)
                except json.JSONDecodeError:
                    parsed_content = None
                if not isinstance(parsed_content, dict):
                    errors.append(
                        invalid_value(
                            "event.content",
                            "identity event.content must be a JSON object string",
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
