from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openprints_cli.event_types import DraftEvent, SignedEvent


class Signer(Protocol):
    def sign_event(self, event: DraftEvent) -> SignedEvent:
        """Return a signed event with pubkey, id, and sig fields."""


@dataclass(slots=True)
class SignerError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message
