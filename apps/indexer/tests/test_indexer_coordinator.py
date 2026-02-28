"""Tests for openprints.indexer.design_indexer."""

from __future__ import annotations

import asyncio

from openprints.indexer.design_indexer import DesignIndexer
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


def test_design_indexer_init() -> None:
    indexer = DesignIndexer(
        relays=["ws://localhost:7447"],
        kind=33301,
        timeout_s=2.0,
        queue_maxsize=10,
        max_retries=3,
    )
    assert indexer.relays == ["ws://localhost:7447"]
    assert indexer.kind == 33301
    assert indexer.timeout_s == 2.0
    assert indexer.max_retries == 3
    assert indexer.reducer is not None


def test_design_indexer_run_starts_and_stops(monkeypatch) -> None:
    import openprints.indexer.design_indexer as indexer_mod

    monkeypatch.setattr(indexer_mod, "RelayWorker", _InstantRelayWorker)
    indexer = DesignIndexer(
        relays=["ws://localhost:7447"],
        kind=33301,
        queue_maxsize=10,
        max_retries=1,
    )

    async def run_then_stop() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(indexer.run(stop_event))
        await asyncio.sleep(0.05)
        stop_event.set()
        await task

    asyncio.run(run_then_stop())
    assert indexer.reducer.stats.processed >= 0


def test_design_indexer_stop_clears_tasks(monkeypatch) -> None:
    import openprints.indexer.design_indexer as indexer_mod

    monkeypatch.setattr(indexer_mod, "RelayWorker", _InstantRelayWorker)
    indexer = DesignIndexer(
        relays=["ws://localhost:7447"],
        kind=33301,
        queue_maxsize=10,
        max_retries=1,
    )

    async def start_then_stop() -> None:
        indexer._stop_event = asyncio.Event()
        await indexer._start()
        assert len(indexer._worker_tasks) > 0
        assert indexer._reducer_task is not None
        indexer._stop_event.set()
        await indexer.stop()
        assert len(indexer._worker_tasks) == 0
        assert indexer._reducer_task is None

    asyncio.run(start_then_stop())


def test_design_indexer_accepts_custom_store() -> None:
    store = LogOnlyIndexStore()
    indexer = DesignIndexer(
        relays=["ws://localhost:7447"],
        kind=33301,
        store=store,
    )
    assert indexer.reducer._store is store
