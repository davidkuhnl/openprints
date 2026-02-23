from __future__ import annotations

import os
from argparse import Namespace

from openprints.common.errors import invalid_value


def resolve_relay_urls(
    cli_relays: list[str] | None,
    *,
    configured_relays: list[str] | None = None,
    include_env: bool = True,
    default_relays: list[str] | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    relays: list[str] = []
    if cli_relays:
        relays = [value.strip() for value in cli_relays if value and value.strip()]

    if not relays and include_env:
        single = os.environ.get("OPENPRINTS_RELAY_URL", "").strip()
        if single:
            relays = [single]

    if not relays and include_env:
        relay_list = os.environ.get("OPENPRINTS_RELAY_URLS", "").strip()
        if relay_list:
            relays = [value.strip() for value in relay_list.split(",") if value.strip()]

    if not relays:
        relays = [value.strip() for value in (configured_relays or []) if value and value.strip()]

    if not relays:
        relays = default_relays or ["ws://localhost:7447"]

    for relay in relays:
        if not (relay.startswith("ws://") or relay.startswith("wss://")):
            return [], [invalid_value("relay", "relay URL must start with ws:// or wss://")]

    # Preserve input order while removing duplicates.
    return list(dict.fromkeys(relays)), []


def resolve_relay_url(args: Namespace) -> tuple[str | None, list[dict[str, str]]]:
    relay_input = (args.relay or "").strip()
    relay_urls, errors = resolve_relay_urls([relay_input] if relay_input else None)
    if errors:
        return None, errors
    return relay_urls[0], []
