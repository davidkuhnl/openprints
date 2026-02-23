"""Tests for openprints.common.event_filter."""

from openprints.common.event_filter import is_ingestible_design_event
from tests.test_helpers import valid_signed_payload


def test_accepts_valid_design_event() -> None:
    payload = valid_signed_payload()
    assert is_ingestible_design_event(payload["event"]) is True


def test_rejects_missing_id() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    del event["id"]
    assert is_ingestible_design_event(event) is False


def test_rejects_missing_pubkey() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    del event["pubkey"]
    assert is_ingestible_design_event(event) is False


def test_rejects_non_string_id() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["id"] = 12345
    assert is_ingestible_design_event(event) is False


def test_rejects_non_string_pubkey() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["pubkey"] = 12345
    assert is_ingestible_design_event(event) is False


def test_rejects_missing_d_tag() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["tags"] = [["name", "Only name"], ["format", "stl"]]
    assert is_ingestible_design_event(event) is False


def test_rejects_non_openprints_d_tag() -> None:
    """Event with d tag that is not openprints:uuid-v4 is not ingestible."""
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["tags"] = [
        ["d", "openprints:abc"],
        ["name", "x"],
        ["format", "stl"],
        ["sha256", "0" * 64],
        ["url", "https://x"],
    ]
    assert is_ingestible_design_event(event) is False


def test_rejects_non_int_kind() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["kind"] = "33301"
    assert is_ingestible_design_event(event) is False


def test_rejects_non_int_created_at() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["created_at"] = "1730000000"
    assert is_ingestible_design_event(event) is False
