import asyncio
import json
import os
import sys
import time
from argparse import Namespace
from pathlib import Path

import websockets

from openprints_cli.errors import invalid_json, invalid_value
from openprints_cli.event_utils import verify_event_signature
from openprints_cli.payload_contract import validate_payload


def _read_input(input_value: str) -> str:
    if input_value == "-":
        return sys.stdin.read()
    return Path(input_value).read_text(encoding="utf-8")


def _resolve_relay_url(args: Namespace) -> tuple[str | None, list[dict[str, str]]]:
    relay = (args.relay or "").strip()
    if not relay:
        relay = os.environ.get("OPENPRINTS_RELAY_URL", "").strip()
    if not relay:
        relay_list = os.environ.get("OPENPRINTS_RELAY_URLS", "").strip()
        if relay_list:
            relay = relay_list.split(",")[0].strip()
    if not relay:
        relay = "ws://localhost:7447"

    if not (relay.startswith("ws://") or relay.startswith("wss://")):
        return None, [invalid_value("relay", "relay URL must start with ws:// or wss://")]

    return relay, []


async def _publish_event_to_relay(relay: str, event: dict, timeout_s: float) -> dict[str, object]:
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
            "message": f"relay returned non-JSON response: {raw}",
        }

    if not isinstance(message, list) or len(message) < 4 or message[0] != "OK":
        return {
            "relay": relay,
            "event_id": event_id,
            "accepted": False,
            "message": f"relay returned unexpected response: {message}",
        }

    relay_event_id = str(message[1])
    accepted = bool(message[2])
    relay_message = str(message[3])
    if relay_event_id and relay_event_id != event_id:
        accepted = False
        relay_message = f"relay acknowledged different event id: {relay_event_id}"

    return {
        "relay": relay,
        "event_id": event_id,
        "accepted": accepted,
        "message": relay_message,
    }


def run_publish(args: Namespace) -> int:
    raw_payload = _read_input(args.input)
    if not raw_payload.strip():
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_json("$", "input is empty")],
                },
                indent=2,
            )
        )
        return 1

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_json("$", f"input is not valid JSON ({exc})")],
                },
                indent=2,
            )
        )
        return 1

    errors = validate_payload(payload)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1

    state = payload.get("meta", {}).get("state")
    if state != "signed":
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_value("meta.state", "publish expects a signed payload")],
                },
                indent=2,
            )
        )
        return 1

    sig_error = verify_event_signature(payload["event"])
    if sig_error is not None:
        print(
            json.dumps(
                {"ok": False, "errors": [invalid_value("event", sig_error)]},
                indent=2,
            )
        )
        return 1

    relay, relay_errors = _resolve_relay_url(args)
    if relay_errors:
        print(json.dumps({"ok": False, "errors": relay_errors}, indent=2))
        return 1

    retries = max(0, int(args.retries))
    retry_backoff_s = max(0.0, int(args.retry_backoff_ms) / 1000.0)

    relay_result: dict[str, object] | None = None
    last_transport_error: str | None = None
    for attempt in range(retries + 1):
        try:
            relay_result = asyncio.run(
                _publish_event_to_relay(relay, payload["event"], args.timeout)
            )
        except Exception as exc:
            last_transport_error = f"publish transport error: {exc}"
            if attempt < retries:
                time.sleep(retry_backoff_s)
                continue
            relay_result = {
                "relay": relay,
                "event_id": str(payload.get("event", {}).get("id", "")),
                "accepted": False,
                "message": last_transport_error,
            }
            break

        # Intentional behavior: do not retry relay-level rejections.
        if relay_result["accepted"]:
            break
        if attempt < retries:
            break

    if relay_result is None:
        relay_result = {
            "relay": relay,
            "event_id": str(payload.get("event", {}).get("id", "")),
            "accepted": False,
            "message": "publish failed with unknown state",
        }

    if last_transport_error and not relay_result["accepted"]:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_value("relay", relay_result["message"])],
                    "relay_results": [relay_result],
                },
                indent=2,
            )
        )
        return 1

    if not relay_result["accepted"]:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_value("relay", str(relay_result["message"]))],
                    "relay_results": [relay_result],
                },
                indent=2,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "relay_results": [relay_result],
            },
            indent=2,
        )
    )
    return 0
