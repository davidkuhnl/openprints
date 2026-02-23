from __future__ import annotations

import asyncio
import json
import logging
import secrets
import sys
from argparse import Namespace

import websockets  # type: ignore[reportMissingImports]
from websockets.exceptions import ConnectionClosed  # type: ignore[reportMissingImports]

from openprints.common.errors import invalid_value
from openprints.common.utils.logging import configure_logging
from openprints.common.utils.output import print_json
from openprints.common.utils.relay import resolve_relay_url

logger = logging.getLogger(__name__)


async def _subscribe_once(
    relay: str,
    kind: int,
    timeout_s: float,
    limit: int,
) -> dict[str, object]:
    sub_id = f"openprints-cli-{secrets.token_hex(4)}"
    req_message = ["REQ", sub_id, {"kinds": [kind]}]
    logger.info(
        "subscribe_connection_opening",
        extra={
            "relay": relay,
            "kind": kind,
            "limit": limit,
            "timeout_s": timeout_s,
            "sub_id": sub_id,
        },
    )

    events_seen = 0
    eose_seen = False

    async with websockets.connect(relay, open_timeout=timeout_s, close_timeout=timeout_s) as ws:
        await ws.send(json.dumps(req_message, separators=(",", ":"), ensure_ascii=False))
        logger.debug(
            "subscribe_request_sent",
            extra={"relay": relay, "sub_id": sub_id, "kind": kind},
        )
        while True:
            if limit > 0 and events_seen >= limit:
                await ws.send(
                    json.dumps(["CLOSE", sub_id], separators=(",", ":"), ensure_ascii=False)
                )
                logger.info(
                    "subscribe_limit_reached",
                    extra={
                        "relay": relay,
                        "sub_id": sub_id,
                        "events_seen": events_seen,
                        "limit": limit,
                    },
                )
                break

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
            except asyncio.TimeoutError:
                logger.info(
                    "subscribe_receive_timeout",
                    extra={
                        "relay": relay,
                        "sub_id": sub_id,
                        "events_seen": events_seen,
                        "timeout_s": timeout_s,
                    },
                )
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
                logger.debug(
                    "subscribe_event_received",
                    extra={"relay": relay, "sub_id": sub_id, "events_seen": events_seen},
                )
            elif msg_type == "EOSE" and len(message) >= 2 and message[1] == sub_id:
                eose_seen = True
                logger.info(
                    "subscribe_eose_received",
                    extra={"relay": relay, "sub_id": sub_id, "events_seen": events_seen},
                )
                # Keep streaming after EOSE in live mode (limit=0). EOSE only marks
                # completion of the initial backlog, not the end of subscription.
            elif msg_type == "NOTICE" and len(message) >= 2:
                print_json(
                    {"relay": relay, "type": "NOTICE", "message": str(message[1])},
                    stream=sys.stderr,
                )
                logger.info("subscribe_notice_received", extra={"relay": relay, "sub_id": sub_id})

    logger.info(
        "subscribe_connection_closed",
        extra={
            "relay": relay,
            "sub_id": sub_id,
            "events_seen": events_seen,
            "eose_seen": eose_seen,
        },
    )
    return {"relay": relay, "events_seen": events_seen, "eose_seen": eose_seen}


def run_subscribe(args: Namespace) -> int:
    configure_logging()
    relay, relay_errors = resolve_relay_url(args)
    if relay_errors:
        print_json({"ok": False, "errors": relay_errors})
        return 1

    logger.info(
        "subscribe_start",
        extra={"relay": relay, "kind": args.kind, "limit": args.limit, "timeout_s": args.timeout},
    )
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
        logger.info("subscribe_interrupted_by_user", extra={"relay": relay})
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
        logger.info(
            "subscribe_relay_disconnected",
            extra={"relay": relay, "disconnect_reason": str(exc)},
        )
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
        logger.exception("subscribe_transport_error", extra={"relay": relay})
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("relay", f"subscribe transport error: {exc}")],
                "relay_results": [{"relay": relay, "events_seen": 0, "eose_seen": False}],
            }
        )
        return 1

    logger.info(
        "subscribe_complete",
        extra={
            "relay": relay,
            "events_seen": result.get("events_seen"),
            "eose_seen": result.get("eose_seen"),
        },
    )
    print_json({"ok": True, "relay_results": [result]}, stream=sys.stderr)
    return 0
