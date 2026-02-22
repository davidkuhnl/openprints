"""Shared Nostr event serialization and verification (NIP-01)."""

from __future__ import annotations

import hashlib
import json

from coincurve import PublicKeyXOnly


def canonical_event_serialization(event: dict, pubkey: str) -> bytes:
    """Serialize event for hashing (id) and signing. Order and format must match NIP-01."""
    payload = [
        0,
        pubkey,
        event["created_at"],
        event["kind"],
        event["tags"],
        event["content"],
    ]
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_event_id(event: dict, pubkey: str) -> str:
    """Compute the Nostr event id (SHA256 of canonical serialization) as hex."""
    serialized = canonical_event_serialization(event, pubkey)
    return hashlib.sha256(serialized).hexdigest()


def verify_event_signature(event: dict) -> str | None:
    """
    Verify event id and Schnorr signature. Returns None if valid, else an error message.
    Event must already contain id, pubkey, sig.
    """
    pubkey_hex = event.get("pubkey")
    if not pubkey_hex or not isinstance(pubkey_hex, str) or len(pubkey_hex) != 64:
        return "event.pubkey missing or invalid (expected 64-char hex)"
    try:
        pubkey_bytes = bytes.fromhex(pubkey_hex)
    except ValueError:
        return "event.pubkey is not valid hex"

    computed_id = compute_event_id(event, pubkey_hex)
    event_id = event.get("id")
    if not event_id or event_id != computed_id:
        return f"event id mismatch (computed {computed_id})"

    sig_hex = event.get("sig")
    if not sig_hex or not isinstance(sig_hex, str) or len(sig_hex) != 128:
        return "event.sig missing or invalid (expected 128-char hex)"
    try:
        sig_bytes = bytes.fromhex(sig_hex)
    except ValueError:
        return "event.sig is not valid hex"
    if len(sig_bytes) != 64:
        return "event.sig must be 64 bytes"

    try:
        pub = PublicKeyXOnly(pubkey_bytes)
    except ValueError as e:
        return f"invalid event.pubkey: {e}"

    message = bytes.fromhex(computed_id)
    if not pub.verify(sig_bytes, message):
        return "signature verification failed"

    return None
