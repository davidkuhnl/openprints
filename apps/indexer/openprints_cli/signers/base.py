from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Signer(Protocol):
    def sign_event(self, event: dict) -> dict:
        """Return a signed event with pubkey, id, and sig fields."""


@dataclass(slots=True)
class SignerError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message
