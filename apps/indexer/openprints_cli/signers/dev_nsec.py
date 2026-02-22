from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from bech32 import bech32_decode, convertbits
from coincurve import PrivateKey

from openprints_cli.signers.base import SignerError


def _decode_nsec(nsec: str) -> bytes:
    hrp, data = bech32_decode(nsec.strip())
    if hrp != "nsec" or data is None:
        raise SignerError("invalid nsec: expected bech32 string with nsec prefix")

    raw = convertbits(data, 5, 8, False)
    if raw is None:
        raise SignerError("invalid nsec: cannot convert bech32 data")

    secret = bytes(raw)
    if len(secret) != 32:
        raise SignerError("invalid nsec: secret key must be 32 bytes")
    return secret


def _canonical_event_serialization(event: dict, pubkey: str) -> bytes:
    payload = [
        0,
        pubkey,
        event["created_at"],
        event["kind"],
        event["tags"],
        event["content"],
    ]
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(slots=True)
class DevNsecSigner:
    _private_key: PrivateKey

    @classmethod
    def from_nsec(cls, nsec: str) -> "DevNsecSigner":
        secret = _decode_nsec(nsec)
        return cls(_private_key=PrivateKey(secret))

    def sign_event(self, event: dict) -> dict:
        pubkey = self._private_key.public_key_xonly.format().hex()
        serialized = _canonical_event_serialization(event, pubkey)
        event_id = hashlib.sha256(serialized).hexdigest()
        signature = self._private_key.sign_schnorr(
            bytes.fromhex(event_id),
            aux_randomness=b"\x00" * 32,
        ).hex()

        signed = dict(event)
        signed["pubkey"] = pubkey
        signed["id"] = event_id
        signed["sig"] = signature
        return signed
