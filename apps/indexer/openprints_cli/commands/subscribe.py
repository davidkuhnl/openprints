from __future__ import annotations

import asyncio
import json
import secrets
import sys
from argparse import Namespace

import websockets  # type: ignore[reportMissingImports]
from websockets.exceptions import ConnectionClosed  # type: ignore[reportMissingImports]

from openprints_cli.errors import invalid_value
from openprints_cli.utils.output import print_json
from openprints_cli.utils.relay import resolve_relay_url


async def _subscribe_once(
    relay: str,
    kind: int,
    timeout_s: float,
    limit: int,
) -> dict[str, object]:
    sub_id = f"openprints-cli-{secrets.token_hex(4)}"
    req_message = ["REQ", sub_id, {"kinds": [kind]}]

    events_seen = 0
    eose_seen = False

    async with websockets.connect(relay, open_timeout=timeout_s, close_timeout=timeout_s) as ws:
        await ws.send(json.dumps(req_message, separators=(",", ":"), ensure_ascii=False))
        while True:
            if limit > 0 and events_seen >= limit:
                await ws.send(
                    json.dumps(["CLOSE", sub_id], separators=(",", ":"), ensure_ascii=False)
                )
                break

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
            except asyncio.TimeoutError:
                break

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                print_json({"relay": relay, "type": "MALFORMED", "raw": raw}, stream=sys.stderr)
                continue

            if not isinstance(message, list) or not message:
                continue

            msg_type = message[0]
            if msg_type == "EVENT" and len(message) >= 3 and message[1] == sub_id:
                event = message[2]
                print_json(event, compact=True, ensure_ascii=False)
                events_seen += 1
            elif msg_type == "EOSE" and len(message) >= 2 and message[1] == sub_id:
                eose_seen = True
                # Keep streaming after EOSE in live mode (limit=0). EOSE only marks
                # completion of the initial backlog, not the end of subscription.
            elif msg_type == "NOTICE" and len(message) >= 2:
                print_json(
                    {"relay": relay, "type": "NOTICE", "message": str(message[1])},
                    stream=sys.stderr,
                )

    return {"relay": relay, "events_seen": events_seen, "eose_seen": eose_seen}


def run_subscribe(args: Namespace) -> int:
    relay, relay_errors = resolve_relay_url(args)
    if relay_errors:
        print_json({"ok": False, "errors": relay_errors})
        return 1

    try:
        result = asyncio.run(
            _subscribe_once(
                relay=relay,
                kind=args.kind,
                timeout_s=args.timeout,
                limit=args.limit,
            )
        )
    except KeyboardInterrupt:
        print_json(
            {
                "ok": True,
                "relay_results": [
                    {
                        "relay": relay,
                        "events_seen": 0,
                        "eose_seen": False,
                        "status": "interrupted",
                        "message": "subscription interrupted by user",
                    }
                ],
            },
            stream=sys.stderr,
        )
        return 0
    except ConnectionClosed as exc:
        # Graceful shutdown path when relay disconnects. This is where future
        # reconnect logic will be plugged in for long-lived subscribers.
        print_json(
            {
                "ok": True,
                "relay_results": [
                    {
                        "relay": relay,
                        "events_seen": 0,
                        "eose_seen": False,
                        "status": "disconnected",
                        "message": str(exc),
                    }
                ],
            },
            stream=sys.stderr,
        )
        return 0
    except Exception as exc:
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("relay", f"subscribe transport error: {exc}")],
                "relay_results": [{"relay": relay, "events_seen": 0, "eose_seen": False}],
            }
        )
        return 1

    print_json({"ok": True, "relay_results": [result]}, stream=sys.stderr)
    return 0
