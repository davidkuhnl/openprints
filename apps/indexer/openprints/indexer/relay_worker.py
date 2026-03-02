from __future__ import annotations

import asyncio
import logging
import time
from typing import cast

import websockets

from openprints.common.event_filter import is_ingestible_design_event
from openprints.common.event_types import SignedEvent
from openprints.common.relay_protocol import (
    build_req,
    consume_messages,
    new_sub_id,
    serialize_message,
)
from openprints.common.utils.async_helpers import stop_aware_sleep

from .types import IngestEnvelope

logger = logging.getLogger(__name__)


class RelayWorker:
    def __init__(
        self,
        *,
        relay: str,
        kind: int,
        timeout_s: float,
        max_retries: int,
        out_queue: asyncio.Queue[IngestEnvelope],
        stop_event: asyncio.Event,
    ) -> None:
        self.relay = relay
        self.kind = kind
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.out_queue = out_queue
        self.stop_event = stop_event

    async def run(self) -> None:
        backoff_s = 0.5
        consecutive_failures = 0
        while not self.stop_event.is_set():
            sub_id = new_sub_id("indexer")
            try:
                logger.info("relay_connecting", extra={"relay": self.relay, "kind": self.kind})
                async with websockets.connect(
                    self.relay,
                    open_timeout=self.timeout_s,
                    close_timeout=self.timeout_s,
                ) as ws:
                    await ws.send(serialize_message(build_req(sub_id, self.kind)))
                    logger.info("relay_connected", extra={"relay": self.relay, "sub_id": sub_id})
                    backoff_s = 0.5
                    consecutive_failures = 0
                    await consume_messages(
                        ws,
                        self.relay,
                        sub_id,
                        self.timeout_s,
                        on_event=self._on_event,
                        should_stop=self.stop_event.is_set,
                        timeout_breaks_loop=False,
                        on_malformed=lambda raw: logger.debug(
                            "relay_malformed_message", extra={"relay": self.relay}
                        ),
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consecutive_failures += 1
                logger.warning(
                    (
                        "relay_worker_error relay=%s failure=%d max_retries=%d "
                        "backoff_s=%.1f error=%s"
                    ),
                    self.relay,
                    consecutive_failures,
                    self.max_retries,
                    backoff_s,
                    exc,
                )
                if self.max_retries > 0 and consecutive_failures >= self.max_retries:
                    logger.error(
                        "relay_worker_giving_up relay=%s after %d failures",
                        self.relay,
                        consecutive_failures,
                    )
                    self.stop_event.set()
                    return
                await stop_aware_sleep(self.stop_event, backoff_s)
                backoff_s = min(backoff_s * 2.0, 10.0)

    async def _on_event(self, relay: str, sub_id: str, event: dict, events_seen: int) -> bool:
        if not is_ingestible_design_event(event):
            return False
        envelope = IngestEnvelope(
            relay=relay,
            received_at=int(time.time()),
            event=cast(SignedEvent, event),
        )
        await self.out_queue.put(envelope)
        return False
