"""Tests for openprints.indexer.relay_worker."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from openprints.indexer.relay_worker import RelayWorker
from openprints.indexer.types import IngestEnvelope
from tests.test_helpers import valid_signed_payload


def test_relay_worker_put_envelope_when_event_received() -> None:
    """When mock ws.recv returns an EVENT message, worker puts envelope in queue."""
    queue: asyncio.Queue[IngestEnvelope] = asyncio.Queue()
    stop = asyncio.Event()
    payload = valid_signed_payload()
    event = payload["event"]
    sent: list[str] = []

    async def mock_send(msg: str) -> None:
        sent.append(msg)

    async def mock_recv() -> str:
        if sent:
            req = json.loads(sent[0])
            sub_id = req[1] if isinstance(req, list) and len(req) >= 2 else "fallback"
        else:
            sub_id = "fallback"
        stop.set()
        return json.dumps(["EVENT", sub_id, event], separators=(",", ":"), ensure_ascii=False)

    mock_ws = MagicMock()
    mock_ws.send = AsyncMock(side_effect=mock_send)
    mock_ws.recv = AsyncMock(side_effect=mock_recv)

    class MockConnect:
        async def __aenter__(self) -> MagicMock:
            return mock_ws

        async def __aexit__(self, *args: object) -> None:
            pass

    worker = RelayWorker(
        relay="ws://localhost:7447",
        kind=33301,
        timeout_s=1.0,
        max_retries=0,
        out_queue=queue,
        stop_event=stop,
    )

    async def run_worker() -> None:
        with patch(
            "openprints.indexer.relay_worker.websockets.connect",
            return_value=MockConnect(),
        ):
            await worker.run()

    asyncio.run(run_worker())
    assert queue.qsize() == 1
    envelope = queue.get_nowait()
    assert envelope.relay == "ws://localhost:7447"
    assert envelope.event.get("id") == event["id"]


def test_relay_worker_ignores_non_event_message() -> None:
    """When ws.recv returns a non-EVENT message, no envelope is put."""
    queue: asyncio.Queue[IngestEnvelope] = asyncio.Queue()
    stop = asyncio.Event()
    call_count = 0

    async def mock_recv() -> str:
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            stop.set()
        return json.dumps(["NOTICE", "some message"])

    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=mock_recv)

    class MockConnect:
        async def __aenter__(self) -> MagicMock:
            return mock_ws

        async def __aexit__(self, *args: object) -> None:
            pass

    worker = RelayWorker(
        relay="ws://localhost:7447",
        kind=33301,
        timeout_s=0.5,
        max_retries=0,
        out_queue=queue,
        stop_event=stop,
    )

    async def run_worker() -> None:
        with patch(
            "openprints.indexer.relay_worker.websockets.connect",
            return_value=MockConnect(),
        ):
            await worker.run()

    asyncio.run(run_worker())
    assert queue.qsize() == 0


def test_relay_worker_ignores_malformed_json() -> None:
    """When ws.recv returns invalid JSON, worker continues without putting envelope."""
    queue: asyncio.Queue[IngestEnvelope] = asyncio.Queue()
    stop = asyncio.Event()
    call_count = 0

    async def mock_recv() -> str:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            stop.set()
        return "not valid json {"

    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=mock_recv)

    class MockConnect:
        async def __aenter__(self) -> MagicMock:
            return mock_ws

        async def __aexit__(self, *args: object) -> None:
            pass

    worker = RelayWorker(
        relay="ws://localhost:7447",
        kind=33301,
        timeout_s=0.5,
        max_retries=0,
        out_queue=queue,
        stop_event=stop,
    )

    async def run_worker() -> None:
        with patch(
            "openprints.indexer.relay_worker.websockets.connect",
            return_value=MockConnect(),
        ):
            await worker.run()

    asyncio.run(run_worker())
    assert queue.qsize() == 0
