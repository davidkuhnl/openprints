from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import cast

import websockets

from openprints.common.event_types import SignedEvent

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
            sub_id = f"openprints-indexer-{int(time.time() * 1000)}"
            req_message = ["REQ", sub_id, {"kinds": [self.kind]}]
            try:
                logger.info("relay_connecting", extra={"relay": self.relay, "kind": self.kind})
                async with websockets.connect(
                    self.relay,
                    open_timeout=self.timeout_s,
                    close_timeout=self.timeout_s,
                ) as ws:
                    req_json = json.dumps(req_message, separators=(",", ":"), ensure_ascii=False)
                    await ws.send(req_json)
                    logger.info("relay_connected", extra={"relay": self.relay, "sub_id": sub_id})
                    backoff_s = 0.5
                    consecutive_failures = 0
                    await self._consume_messages(ws, sub_id)
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
                await asyncio.sleep(backoff_s)
                backoff_s = min(backoff_s * 2.0, 10.0)

    async def _consume_messages(self, ws: websockets.ClientConnection, sub_id: str) -> None:
        while not self.stop_event.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout_s)
            except asyncio.TimeoutError:
                continue

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.debug("relay_malformed_message", extra={"relay": self.relay})
                continue

            if not isinstance(message, list) or not message:
                continue
            if message[0] != "EVENT" or len(message) < 3:
                continue
            if message[1] != sub_id or not isinstance(message[2], dict):
                continue

            envelope = IngestEnvelope(
                relay=self.relay,
                received_at=int(time.time()),
                event=cast(SignedEvent, message[2]),
            )
            await self.out_queue.put(envelope)
