from __future__ import annotations

import asyncio
import logging
import sys
from argparse import Namespace

import websockets  # type: ignore[reportMissingImports]
from websockets.exceptions import ConnectionClosed  # type: ignore[reportMissingImports]

from openprints.common.errors import invalid_value
from openprints.common.relay_protocol import (
    build_close,
    build_req,
    consume_messages,
    new_sub_id,
    serialize_message,
)
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
    sub_id = new_sub_id("cli")
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

    async with websockets.connect(relay, open_timeout=timeout_s, close_timeout=timeout_s) as ws:
        await ws.send(serialize_message(build_req(sub_id, kind)))
        logger.debug(
            "subscribe_request_sent",
            extra={"relay": relay, "sub_id": sub_id, "kind": kind},
        )

        def on_event(r: str, sid: str, event: dict, events_seen: int) -> bool:
            print_json(event, compact=True, ensure_ascii=False)
            logger.debug(
                "subscribe_event_received",
                extra={"relay": r, "sub_id": sid, "events_seen": events_seen},
            )
            return limit > 0 and events_seen >= limit

        def on_eose(r: str, sid: str, events_seen: int) -> None:
            logger.info(
                "subscribe_eose_received",
                extra={"relay": r, "sub_id": sid, "events_seen": events_seen},
            )

        def on_notice(r: str, message: str) -> None:
            print_json(
                {"relay": r, "type": "NOTICE", "message": message},
                stream=sys.stderr,
            )
            logger.info("subscribe_notice_received", extra={"relay": r, "sub_id": sub_id})

        def on_malformed(raw: str) -> None:
            print_json({"relay": relay, "type": "MALFORMED", "raw": raw}, stream=sys.stderr)

        result = await consume_messages(
            ws,
            relay,
            sub_id,
            timeout_s,
            on_event=on_event,
            on_eose=on_eose,
            on_notice=on_notice,
            should_stop=lambda: False,
            timeout_breaks_loop=True,
            on_malformed=on_malformed,
        )

        if limit > 0 and result["events_seen"] >= limit:
            await ws.send(serialize_message(build_close(sub_id)))
            logger.info(
                "subscribe_limit_reached",
                extra={
                    "relay": relay,
                    "sub_id": sub_id,
                    "events_seen": result["events_seen"],
                    "limit": limit,
                },
            )

    logger.info(
        "subscribe_connection_closed",
        extra={
            "relay": relay,
            "sub_id": sub_id,
            "events_seen": result["events_seen"],
            "eose_seen": result["eose_seen"],
        },
    )
    return {
        "relay": relay,
        "events_seen": result["events_seen"],
        "eose_seen": result["eose_seen"],
    }


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
