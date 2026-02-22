import asyncio
import json
import time
from argparse import Namespace

import websockets

from openprints_cli.errors import invalid_json, invalid_value
from openprints_cli.event_utils import verify_event_signature
from openprints_cli.payload_contract import validate_payload
from openprints_cli.utils.input import read_text_input
from openprints_cli.utils.output import print_json
from openprints_cli.utils.relay import resolve_relay_url


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
    raw_payload = read_text_input(args.input)
    if not raw_payload.strip():
        print_json({"ok": False, "errors": [invalid_json("$", "input is empty")]})
        return 1

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        print_json({"ok": False, "errors": [invalid_json("$", f"input is not valid JSON ({exc})")]})
        return 1

    errors = validate_payload(payload)
    if errors:
        print_json({"ok": False, "errors": errors})
        return 1

    state = payload.get("meta", {}).get("state")
    if state != "signed":
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("meta.state", "publish expects a signed payload")],
            }
        )
        return 1

    sig_error = verify_event_signature(payload["event"])
    if sig_error is not None:
        print_json({"ok": False, "errors": [invalid_value("event", sig_error)]})
        return 1

    relay, relay_errors = resolve_relay_url(args)
    if relay_errors:
        print_json({"ok": False, "errors": relay_errors})
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
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("relay", relay_result["message"])],
                "relay_results": [relay_result],
            }
        )
        return 1

    if not relay_result["accepted"]:
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("relay", str(relay_result["message"]))],
                "relay_results": [relay_result],
            }
        )
        return 1

    print_json({"ok": True, "relay_results": [relay_result]})
    return 0
