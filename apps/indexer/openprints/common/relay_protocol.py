"""Shared Nostr relay wire protocol: REQ/CLOSE, message parse, consume loop."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def new_sub_id(role: str) -> str:
    """Return a unique subscription id for the given role (e.g. 'cli', 'indexer')."""
    return f"openprints-{role}-{secrets.token_hex(4)}"


def build_req(sub_id: str, kind: int) -> list[Any]:
    """Build a REQ message for the given subscription id and kind."""
    return ["REQ", sub_id, {"kinds": [kind]}]


def build_close(sub_id: str) -> list[Any]:
    """Build a CLOSE message for the given subscription id."""
    return ["CLOSE", sub_id]


def serialize_message(msg: list[Any]) -> str:
    """Serialize a REQ/CLOSE-style message for sending to the relay."""
    return json.dumps(msg, separators=(",", ":"), ensure_ascii=False)


def parse_relay_message(
    raw: str,
) -> tuple[str | None, str | None, dict[str, Any] | None, str]:
    """Parse one relay wire message.

    Returns (msg_type, sub_id_or_extra, event_payload, notice_text).
    - EVENT: (\"EVENT\", sub_id, event_dict, \"\")
    - EOSE: (\"EOSE\", sub_id, None, \"\")
    - NOTICE: (\"NOTICE\", \"\", None, notice_message)
    - Malformed: (None, None, None, \"\")
    """
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return (None, None, None, "")

    if not isinstance(message, list) or not message:
        return (None, None, None, "")

    msg_type = message[0] if isinstance(message[0], str) else None
    if not msg_type:
        return (None, None, None, "")

    if msg_type == "EVENT" and len(message) >= 3 and isinstance(message[2], dict):
        sub_id = message[1] if isinstance(message[1], str) else None
        return (msg_type, sub_id, message[2], "")

    if msg_type == "EOSE" and len(message) >= 2:
        sub_id = message[1] if isinstance(message[1], str) else None
        return (msg_type, sub_id, None, "")

    if msg_type == "NOTICE" and len(message) >= 2:
        notice_text = str(message[1])
        return (msg_type, "", None, notice_text)

    return (None, None, None, "")


async def consume_messages(
    ws: Any,
    relay: str,
    sub_id: str,
    timeout_s: float,
    *,
    on_event: Callable[[str, str, dict[str, Any], int], bool],
    on_eose: Callable[[str, str, int], None] | None = None,
    on_notice: Callable[[str, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    timeout_breaks_loop: bool = True,
    on_malformed: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Receive and dispatch relay messages until stop or timeout.

    - on_event(relay, sub_id, event): return True to request stop after this event.
    - on_eose(relay, sub_id): optional.
    - on_notice(relay, message): optional; message is message[1] from NOTICE.
    - should_stop(): checked each iteration; if True, exit loop.
    - timeout_breaks_loop: if True, TimeoutError on recv breaks; else continue.
    - on_malformed(raw): optional; called when parse returns (None, None, None).

    Returns {"events_seen": int, "eose_seen": bool}.
    """
    events_seen = 0
    eose_seen = False

    while True:
        if should_stop and should_stop():
            break

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
        except asyncio.TimeoutError:
            if timeout_breaks_loop:
                break
            continue

        msg_type, parsed_sub_id, event_payload, notice_text = parse_relay_message(raw)

        if msg_type is None:
            if on_malformed:
                on_malformed(raw)
            continue

        if msg_type == "EVENT" and parsed_sub_id == sub_id and event_payload is not None:
            events_seen += 1
            result = on_event(relay, sub_id, event_payload, events_seen)
            if asyncio.iscoroutine(result):
                result = await result
            if result:
                break
        elif msg_type == "EOSE" and parsed_sub_id == sub_id:
            eose_seen = True
            if on_eose:
                on_eose(relay, sub_id, events_seen)
        elif msg_type == "NOTICE" and on_notice:
            on_notice(relay, notice_text)

    return {"events_seen": events_seen, "eose_seen": eose_seen}
