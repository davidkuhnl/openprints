from __future__ import annotations

from dataclasses import dataclass

from openprints.common.event_types import SignedEvent


@dataclass(frozen=True)
class IngestEnvelope:
    relay: str
    received_at: int
    event: SignedEvent
