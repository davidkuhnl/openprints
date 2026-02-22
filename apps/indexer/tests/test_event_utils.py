"""Tests for openprints_cli.event_utils."""

from __future__ import annotations

from openprints_cli.event_utils import (
    canonical_event_serialization,
    compute_event_id,
    verify_event_signature,
)
from tests.test_helpers import valid_signed_payload


def test_verify_event_signature_valid_returns_none() -> None:
    payload = valid_signed_payload()
    event = payload["event"]
    assert verify_event_signature(event) is None


def test_verify_event_signature_missing_pubkey() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    del event["pubkey"]
    msg = verify_event_signature(event)
    assert msg is not None
    assert "pubkey" in msg.lower()


def test_verify_event_signature_pubkey_wrong_length() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["pubkey"] = "ab" * 31  # 62 chars
    msg = verify_event_signature(event)
    assert msg is not None
    assert "64" in msg or "invalid" in msg.lower()


def test_verify_event_signature_pubkey_not_hex() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["pubkey"] = "z" * 64
    msg = verify_event_signature(event)
    assert msg is not None
    assert "hex" in msg.lower() or "invalid" in msg.lower()


def test_verify_event_signature_id_mismatch() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["id"] = "a" * 64
    msg = verify_event_signature(event)
    assert msg is not None
    assert "mismatch" in msg.lower() or "id" in msg.lower()


def test_verify_event_signature_sig_missing() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    del event["sig"]
    msg = verify_event_signature(event)
    assert msg is not None
    assert "sig" in msg.lower()


def test_verify_event_signature_sig_wrong_length() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["sig"] = "ab" * 32  # 64 chars, need 128
    msg = verify_event_signature(event)
    assert msg is not None
    assert "128" in msg or "sig" in msg.lower()


def test_verify_event_signature_sig_not_hex() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["sig"] = "z" * 128
    msg = verify_event_signature(event)
    assert msg is not None
    assert "hex" in msg.lower() or "sig" in msg.lower()


def test_verify_event_signature_sig_verification_fails() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    # Valid hex but wrong signature (flip some bits)
    event["sig"] = event["sig"][:64] + "f" * 64
    msg = verify_event_signature(event)
    assert msg is not None
    assert "verification" in msg.lower() or "signature" in msg.lower()


def test_canonical_event_serialization_roundtrip() -> None:
    payload = valid_signed_payload()
    event = payload["event"]
    pubkey = event["pubkey"]
    serialized = canonical_event_serialization(event, pubkey)
    assert isinstance(serialized, bytes)
    assert len(serialized) > 0


def test_compute_event_id_matches_event_id() -> None:
    payload = valid_signed_payload()
    event = payload["event"]
    pubkey = event["pubkey"]
    computed = compute_event_id(event, pubkey)
    assert computed == event["id"]
