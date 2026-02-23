"""Tests for openprints.indexer.coordinator."""

from __future__ import annotations

import asyncio

from openprints.indexer.coordinator import IndexerCoordinator
from openprints.indexer.store import LogOnlyIndexStore


class _InstantRelayWorker:
    """RelayWorker that does not connect; run() returns immediately."""

    def __init__(
        self,
        *,
        relay: str,
        kind: int,
        timeout_s: float,
        max_retries: int,
        out_queue: asyncio.Queue,
        stop_event: asyncio.Event,
    ) -> None:
        self.relay = relay
        self.kind = kind
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.out_queue = out_queue
        self.stop_event = stop_event

    async def run(self) -> None:
        await asyncio.sleep(0)


def test_coordinator_init() -> None:
    coordinator = IndexerCoordinator(
        relays=["ws://localhost:7447"],
        kind=33301,
        timeout_s=2.0,
        queue_maxsize=10,
        max_retries=3,
    )
    assert coordinator.relays == ["ws://localhost:7447"]
    assert coordinator.kind == 33301
    assert coordinator.timeout_s == 2.0
    assert coordinator.max_retries == 3
    assert coordinator.reducer is not None
    assert not coordinator.stop_event.is_set()


def test_coordinator_run_for_starts_and_stops(monkeypatch) -> None:
    import openprints.indexer.coordinator as coord_mod

    monkeypatch.setattr(coord_mod, "RelayWorker", _InstantRelayWorker)
    coordinator = IndexerCoordinator(
        relays=["ws://localhost:7447"],
        kind=33301,
        queue_maxsize=10,
        max_retries=1,
    )
    asyncio.run(coordinator.run_for(0.05))
    assert coordinator.stop_event.is_set()
    assert coordinator.reducer.stats.processed >= 0


def test_coordinator_stop_clears_tasks(monkeypatch) -> None:
    import openprints.indexer.coordinator as coord_mod

    monkeypatch.setattr(coord_mod, "RelayWorker", _InstantRelayWorker)
    coordinator = IndexerCoordinator(
        relays=["ws://localhost:7447"],
        kind=33301,
        queue_maxsize=10,
        max_retries=1,
    )

    async def start_then_stop() -> None:
        await coordinator._start()
        assert len(coordinator._worker_tasks) > 0
        assert coordinator._reducer_task is not None
        await coordinator.stop()
        assert len(coordinator._worker_tasks) == 0
        assert coordinator._reducer_task is None

    asyncio.run(start_then_stop())


def test_coordinator_accepts_custom_store() -> None:
    store = LogOnlyIndexStore()
    coordinator = IndexerCoordinator(
        relays=["ws://localhost:7447"],
        kind=33301,
        store=store,
    )
    assert coordinator.reducer._store is store
