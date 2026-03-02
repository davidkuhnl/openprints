from __future__ import annotations

from bech32 import bech32_encode, convertbits


def to_npub(pubkey: str) -> str | None:
    """Convert 64-char hex pubkey to npub bech32 string, or None if invalid."""
    if len(pubkey) != 64:
        return None
    try:
        pubkey_bytes = bytes.fromhex(pubkey)
    except ValueError:
        return None
    data = convertbits(pubkey_bytes, 8, 5, True)
    if data is None:
        return None
    return bech32_encode("npub", data)


def truncate_middle(value: str, max_chars: int = 10) -> str:
    """Truncate in the middle: first x chars + … + last y chars, x + y = max_chars."""
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    x = (max_chars + 1) // 2
    y = max_chars // 2
    return value[:x] + "…" + value[-y:]


def non_empty_string(value: object | None) -> str | None:
    """Return trimmed string or None if empty/non-string."""
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None
