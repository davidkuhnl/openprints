from __future__ import annotations

import asyncio
import logging

from .reducer import ReducerWorker
from .relay_worker import RelayWorker
from .store import IndexStore
from .types import IngestEnvelope

logger = logging.getLogger(__name__)


class IndexerCoordinator:
    def __init__(
        self,
        *,
        relays: list[str],
        kind: int = 33301,
        timeout_s: float = 8.0,
        queue_maxsize: int = 1000,
        max_retries: int = 12,
        store: IndexStore | None = None,
    ) -> None:
        self.relays = relays
        self.kind = kind
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.stop_event = asyncio.Event()
        self.queue: asyncio.Queue[IngestEnvelope] = asyncio.Queue(maxsize=queue_maxsize)
        self.reducer = ReducerWorker(store=store)
        self._worker_tasks: list[asyncio.Task] = []
        self._reducer_task: asyncio.Task | None = None

    async def run_for(self, duration_s: float) -> None:
        await self._start()
        try:
            await asyncio.sleep(duration_s)
        finally:
            await self.stop()

    async def run_until_cancelled(self) -> None:
        await self._start()
        try:
            while not self.stop_event.is_set():
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            await self.stop()
            raise
        except KeyboardInterrupt:
            await self.stop()

    async def stop(self) -> None:
        self.stop_event.set()
        for task in self._worker_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()

        if self._reducer_task is not None:
            await self._reducer_task
            self._reducer_task = None

    async def _start(self) -> None:
        logger.info("indexer_starting", extra={"relay_count": len(self.relays), "kind": self.kind})
        self._reducer_task = asyncio.create_task(self._run_reducer(), name="indexer-reducer")
        for relay in self.relays:
            worker = RelayWorker(
                relay=relay,
                kind=self.kind,
                timeout_s=self.timeout_s,
                max_retries=self.max_retries,
                out_queue=self.queue,
                stop_event=self.stop_event,
            )
            task = asyncio.create_task(worker.run(), name=f"relay-worker:{relay}")
            self._worker_tasks.append(task)

    async def _run_reducer(self) -> None:
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                envelope = await asyncio.wait_for(self.queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            try:
                await self.reducer.reduce_one(envelope)
            finally:
                self.queue.task_done()

        logger.info(
            "indexer_stopped",
            extra={
                "processed": self.reducer.stats.processed,
                "reduced": self.reducer.stats.reduced,
                "duplicates": self.reducer.stats.duplicates,
            },
        )
