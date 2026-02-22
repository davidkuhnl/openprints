from __future__ import annotations

import os
from argparse import Namespace

from openprints_cli.errors import invalid_value


def resolve_relay_url(args: Namespace) -> tuple[str | None, list[dict[str, str]]]:
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
