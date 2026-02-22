from __future__ import annotations

from copy import deepcopy

from openprints_cli.error_codes import (
    DRAFT_CONTAINS_SIGNED_FIELDS,
    INVALID_TYPE,
    MISSING_REQUIRED_TAG,
    SIGNED_MISSING_SIGNATURE_FIELDS,
    UNSUPPORTED_ARTIFACT_VERSION,
    UNSUPPORTED_EVENT_KIND,
)
from openprints_cli.payload_contract import ARTIFACT_VERSION, validate_payload


def _base_draft_payload() -> dict:
    return {
        "artifact_version": ARTIFACT_VERSION,
        "meta": {"state": "draft", "source": "openprints-cli"},
        "event": {
            "kind": 33301,
            "created_at": 1730000000,
            "tags": [
                ["d", "openprints:abc"],
                ["name", "Phone Stand"],
                ["format", "stl"],
                ["sha256", "0" * 64],
                ["url", "https://example.invalid/file.stl"],
            ],
            "content": "hello",
        },
    }


def test_validate_payload_accepts_valid_draft() -> None:
    errors = validate_payload(_base_draft_payload())
    assert errors == []


def test_validate_payload_accepts_valid_signed() -> None:
    payload = _base_draft_payload()
    payload["meta"]["state"] = "signed"
    payload["event"]["id"] = "a" * 64
    payload["event"]["sig"] = "b" * 128
    payload["event"]["pubkey"] = "c" * 64

    errors = validate_payload(payload)
    assert errors == []


def test_validate_payload_rejects_non_object_payload() -> None:
    errors = validate_payload("not-an-object")
    assert errors[0]["code"] == INVALID_TYPE


def test_validate_payload_rejects_unsupported_artifact_version() -> None:
    payload = _base_draft_payload()
    payload["artifact_version"] = 999

    errors = validate_payload(payload)
    assert any(err["code"] == UNSUPPORTED_ARTIFACT_VERSION for err in errors)


def test_validate_payload_rejects_missing_meta() -> None:
    payload = _base_draft_payload()
    del payload["meta"]

    errors = validate_payload(payload)
    assert any(err["path"] == "meta" for err in errors)


def test_validate_payload_rejects_invalid_state() -> None:
    payload = _base_draft_payload()
    payload["meta"]["state"] = "invalid"

    errors = validate_payload(payload)
    assert any(err["path"] == "meta.state" for err in errors)


def test_validate_payload_rejects_missing_required_tag() -> None:
    payload = _base_draft_payload()
    payload["event"]["tags"] = [tag for tag in payload["event"]["tags"] if tag[0] != "url"]

    errors = validate_payload(payload)
    assert any(err["code"] == MISSING_REQUIRED_TAG for err in errors)


def test_validate_payload_rejects_name_over_120_chars() -> None:
    payload = _base_draft_payload()
    payload["event"]["tags"] = [
        ["d", "openprints:abc"],
        ["name", "x" * 121],
        ["format", "stl"],
        ["sha256", "0" * 64],
        ["url", "https://example.invalid/file.stl"],
    ]

    errors = validate_payload(payload)
    assert any(err["path"] == "event.tags[name]" for err in errors)


def test_validate_payload_rejects_draft_with_signed_fields() -> None:
    payload = _base_draft_payload()
    payload["event"]["id"] = "a" * 64

    errors = validate_payload(payload)
    assert any(err["code"] == DRAFT_CONTAINS_SIGNED_FIELDS for err in errors)


def test_validate_payload_rejects_signed_missing_signature_fields() -> None:
    payload = _base_draft_payload()
    payload["meta"]["state"] = "signed"

    errors = validate_payload(payload)
    assert any(err["code"] == SIGNED_MISSING_SIGNATURE_FIELDS for err in errors)


def test_validate_payload_rejects_bad_tags_type() -> None:
    payload = _base_draft_payload()
    payload["event"]["tags"] = ["not-a-tag-list"]

    errors = validate_payload(payload)
    assert any(err["path"] == "event.tags" for err in errors)


def test_validate_payload_rejects_non_33301_kind() -> None:
    payload = _base_draft_payload()
    payload["event"]["kind"] = 1

    errors = validate_payload(payload)
    assert any(err["code"] == UNSUPPORTED_EVENT_KIND for err in errors)


def test_validate_payload_rejects_missing_event_required_fields() -> None:
    payload = deepcopy(_base_draft_payload())
    del payload["event"]["content"]
    del payload["event"]["created_at"]

    errors = validate_payload(payload)
    paths = {err["path"] for err in errors}
    assert "event.content" in paths
    assert "event.created_at" in paths
