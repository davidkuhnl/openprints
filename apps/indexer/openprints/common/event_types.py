"""Typed shapes for Nostr events (draft and signed)."""

from __future__ import annotations

from typing import TypedDict


class DraftEvent(TypedDict):
    """Event shape before signing: no id, pubkey, or sig."""

    kind: int
    created_at: int
    tags: list[list[str]]
    content: str


class SignedEvent(TypedDict):
    """Signed event shape: includes id, pubkey, and sig (NIP-01)."""

    id: str
    pubkey: str
    created_at: int
    kind: int
    tags: list[list[str]]
    content: str
    sig: str
