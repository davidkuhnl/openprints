from __future__ import annotations

import asyncio

from .design_indexer import DesignIndexer
from .identity_indexer import IdentityIndexer


class IndexerApp:
    def __init__(
        self,
        *,
        design_indexer: DesignIndexer,
        identity_indexer: IdentityIndexer | None = None,
    ) -> None:
        self.design_indexer = design_indexer
        self.identity_indexer = identity_indexer
        self.stop_event = asyncio.Event()
        self._design_task: asyncio.Task[None] | None = None
        self._identity_task: asyncio.Task[None] | None = None

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
        if self._identity_task is not None:
            await self._identity_task
            self._identity_task = None
        if self._design_task is not None:
            await self._design_task
            self._design_task = None

    async def _start(self) -> None:
        if self._design_task is not None and not self._design_task.done():
            return
        self._design_task = asyncio.create_task(
            self.design_indexer.run(self.stop_event),
            name="design-indexer",
        )
        if self.identity_indexer is not None:
            self._identity_task = asyncio.create_task(
                self.identity_indexer.run(self.stop_event),
                name="identity-indexer",
            )
