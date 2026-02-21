#!/usr/bin/env python3
"""
Nostr WebSocket check for the local relay.
Sends a REQ for kind-1 and expects EOSE or events.

Prerequisites: pip install websockets

Usage: python scripts/test-relay.py [WS_URL]
Example: RELAY_WS_URL=ws://localhost:7447 python scripts/test-relay.py
"""

import asyncio
import json
import os
import sys

WS_URL = os.environ.get("RELAY_WS_URL") or (sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:7447")


async def main():
    try:
        import websockets
    except ImportError:
        print("Missing dependency: pip install websockets", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to {WS_URL} ...")
    try:
        async with websockets.connect(WS_URL, open_timeout=3, close_timeout=2) as ws:
            await ws.send(json.dumps(["REQ", "openprints-test", {"kinds": [1]}]))
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            if isinstance(data, list) and (data[0] == "EOSE" or data[0] == "EVENT"):
                print(f"Relay responded with: {data[0]}")
            print("OK: Nostr WebSocket is working.")
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
