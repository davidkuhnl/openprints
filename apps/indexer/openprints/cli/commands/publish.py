import asyncio
import json
import time
from argparse import Namespace
from typing import cast

import websockets

from openprints.common.errors import invalid_json, invalid_value
from openprints.common.event_types import SignedEvent
from openprints.common.event_utils import verify_event_signature
from openprints.common.payload_contract import validate_payload
from openprints.common.settings import CliOverrides, build_runtime_settings
from openprints.common.utils.input import read_text_input
from openprints.common.utils.output import print_json


async def _publish_event_to_relay(
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

    event = cast(SignedEvent, payload["event"])
    sig_error = verify_event_signature(event)
    if sig_error is not None:
        print_json({"ok": False, "errors": [invalid_value("event", sig_error)]})
        return 1

    cli = CliOverrides(
        relay=[args.relay] if getattr(args, "relay", None) else None,
    )
    _settings, relay_errors, _ = build_runtime_settings(cli=cli)
    if relay_errors or _settings is None:
        print_json(
            {"ok": False, "errors": relay_errors or [{"message": "failed to resolve relay"}]}
        )
        return 1
    relay = _settings.relay_urls[0]

    retries = max(0, int(args.retries))
    retry_backoff_s = max(0.0, int(args.retry_backoff_ms) / 1000.0)

    relay_result: dict[str, object] | None = None
    last_transport_error: str | None = None
    for attempt in range(retries + 1):
        try:
            relay_result = asyncio.run(_publish_event_to_relay(relay, event, args.timeout))
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
