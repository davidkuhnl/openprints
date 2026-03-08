from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets

from openprints.common.event_types import SignedEvent


def _looks_like_duplicate_notice(message: str) -> bool:
    text = (message or "").lower()
    duplicate_markers = (
        "duplicate",
        "already have",
        "already exists",
        "already known",
    )
    return any(marker in text for marker in duplicate_markers)


async def publish_event_to_relay(
    relay: str, event: SignedEvent, timeout_s: float
) -> dict[str, object]:
    event_id = str(event.get("id", ""))
    request = ["EVENT", event]

    async with websockets.connect(relay, open_timeout=timeout_s, close_timeout=timeout_s) as ws:
        await ws.send(json.dumps(request, separators=(",", ":"), ensure_ascii=False))
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)

    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "relay": relay,
            "event_id": event_id,
            "accepted": False,
            "duplicate": False,
            "message": f"relay returned non-JSON response: {raw}",
        }

    if not isinstance(message, list) or len(message) < 4 or message[0] != "OK":
        return {
            "relay": relay,
            "event_id": event_id,
            "accepted": False,
            "duplicate": False,
            "message": f"relay returned unexpected response: {message}",
        }

    relay_event_id = str(message[1])
    accepted = bool(message[2])
    relay_message = str(message[3])
    duplicate = not accepted and _looks_like_duplicate_notice(relay_message)
    if relay_event_id and relay_event_id != event_id:
        accepted = False
        duplicate = False
        relay_message = f"relay acknowledged different event id: {relay_event_id}"

    return {
        "relay": relay,
        "event_id": event_id,
        "accepted": accepted or duplicate,
        "duplicate": duplicate,
        "message": relay_message,
    }


async def publish_event_to_relays(
    relays: list[str],
    event: SignedEvent,
    timeout_s: float = 8.0,
) -> list[dict[str, Any]]:
    async def _publish_one(relay: str) -> dict[str, Any]:
        try:
            return await publish_event_to_relay(relay, event, timeout_s=timeout_s)
        except Exception as exc:
            return {
                "relay": relay,
                "event_id": str(event.get("id", "")),
                "accepted": False,
                "duplicate": False,
                "message": f"publish transport error: {exc}",
            }

    results = await asyncio.gather(*(_publish_one(relay) for relay in relays))
    return [dict(result) for result in results]
