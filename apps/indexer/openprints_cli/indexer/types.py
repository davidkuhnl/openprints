from __future__ import annotations

from dataclasses import dataclass

from openprints_cli.event_types import SignedEvent


@dataclass(frozen=True)
class IngestEnvelope:
    relay: str
    received_at: int
    event: SignedEvent
