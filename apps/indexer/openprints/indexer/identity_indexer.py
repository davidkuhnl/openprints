from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Protocol

import websockets

from openprints.common.relay_protocol import consume_messages, new_sub_id, serialize_message
from openprints.common.utils.async_helpers import stop_aware_sleep

logger = logging.getLogger(__name__)

_PROFILE_FIELDS = (
    "name",
    "display_name",
    "about",
    "picture",
    "banner",
    "website",
    "nip05",
    "lud06",
    "lud16",
)


class IdentityRefreshStore(Protocol):
    async def list_identity_pubkeys_for_refresh(
        self, *, limit: int, stale_after_s: int, now_ts: int
    ) -> list[str]: ...

    async def update_identity_profile(
        self, pubkey: str, metadata: dict[str, str | None], *, fetched_at: int
    ) -> None: ...

    async def mark_identity_fetch_miss(self, pubkey: str, *, attempted_at: int) -> None: ...


@dataclass(frozen=True)
class _ProfileCandidate:
    event_id: str
    created_at: int
    metadata: dict[str, str | None]


def _is_newer_candidate(candidate: _ProfileCandidate, current: _ProfileCandidate) -> bool:
    if candidate.created_at > current.created_at:
        return True
    if candidate.created_at < current.created_at:
        return False
    return candidate.event_id > current.event_id


def _parse_profile_metadata(content: str) -> dict[str, str | None] | None:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    metadata: dict[str, str | None] = {}
    for field in _PROFILE_FIELDS:
        value = payload.get(field)
        metadata[field] = value if isinstance(value, str) else None
    metadata["profile_raw_json"] = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return metadata


async def _fetch_kind0_candidates_from_relay(
    relay: str, pubkeys: list[str], timeout_s: float
) -> dict[str, _ProfileCandidate]:
    if not pubkeys:
        return {}

    sub_id = new_sub_id("identity")
    filter_obj = {"kinds": [0], "authors": pubkeys}
    req_message = ["REQ", sub_id, filter_obj]
    candidates: dict[str, _ProfileCandidate] = {}

    async def _on_event(relay_name: str, _: str, event: dict, __: int) -> bool:
        if event.get("kind") != 0:
            return False
        event_id = event.get("id")
        pubkey = event.get("pubkey")
        created_at = event.get("created_at")
        content = event.get("content")
        if not (
            isinstance(event_id, str)
            and isinstance(pubkey, str)
            and isinstance(created_at, int)
            and isinstance(content, str)
        ):
            return False

        metadata = _parse_profile_metadata(content)
        if metadata is None:
            logger.debug(
                "identity_indexer_invalid_kind0_content",
                extra={"relay": relay_name, "pubkey": pubkey, "event_id": event_id},
            )
            return False

        candidate = _ProfileCandidate(event_id=event_id, created_at=created_at, metadata=metadata)
        existing = candidates.get(pubkey)
        if existing is None or _is_newer_candidate(candidate, existing):
            candidates[pubkey] = candidate
        return False

    try:
        async with websockets.connect(
            relay,
            open_timeout=timeout_s,
            close_timeout=timeout_s,
        ) as ws:
            await ws.send(serialize_message(req_message))
            await consume_messages(
                ws,
                relay,
                sub_id,
                timeout_s,
                on_event=_on_event,
                timeout_breaks_loop=True,
                on_malformed=lambda raw: logger.debug(
                    "identity_indexer_malformed_message", extra={"relay": relay}
                ),
            )
            await ws.send(serialize_message(["CLOSE", sub_id]))
    except Exception as exc:
        logger.warning(
            "identity_indexer_relay_fetch_failed",
            extra={"relay": relay, "error": str(exc)},
        )
        return {}

    return candidates


async def fetch_kind0_for_pubkeys(
    pubkeys: list[str], relays: list[str], *, timeout_s: float = 6.0
) -> dict[str, dict[str, str | None]]:
    if not pubkeys or not relays:
        return {}

    unique_pubkeys = sorted(set(pubkeys))
    relay_results = await asyncio.gather(
        *[_fetch_kind0_candidates_from_relay(relay, unique_pubkeys, timeout_s) for relay in relays]
    )
    merged: dict[str, _ProfileCandidate] = {}
    for result in relay_results:
        for pubkey, candidate in result.items():
            existing = merged.get(pubkey)
            if existing is None or _is_newer_candidate(candidate, existing):
                merged[pubkey] = candidate

    return {pubkey: candidate.metadata for pubkey, candidate in merged.items()}


class IdentityIndexer:
    def __init__(
        self,
        *,
        store: IdentityRefreshStore,
        relays: list[str],
        batch_size: int = 100,
        stale_after_s: int = 24 * 60 * 60,
        poll_interval_s: float = 5.0,
        fetch_timeout_s: float = 6.0,
    ) -> None:
        self._store = store
        self._relays = relays
        self._batch_size = max(1, batch_size)
        self._stale_after_s = max(0, stale_after_s)
        self._poll_interval_s = max(0.25, poll_interval_s)
        self._fetch_timeout_s = max(1.0, fetch_timeout_s)

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info(
            "identity_indexer_starting",
            extra={
                "relay_count": len(self._relays),
                "batch_size": self._batch_size,
                "stale_after_s": self._stale_after_s,
                "poll_interval_s": self._poll_interval_s,
                "fetch_timeout_s": self._fetch_timeout_s,
            },
        )
        try:
            while not stop_event.is_set():
                pubkeys = await self._store.list_identity_pubkeys_for_refresh(
                    limit=self._batch_size,
                    stale_after_s=self._stale_after_s,
                    now_ts=int(time.time()),
                )
                if pubkeys:
                    profiles_by_pubkey = await fetch_kind0_for_pubkeys(
                        pubkeys,
                        self._relays,
                        timeout_s=self._fetch_timeout_s,
                    )
                    attempted_at = int(time.time())
                    fetched_count = 0
                    missed_count = 0
                    for pubkey in pubkeys:
                        metadata = profiles_by_pubkey.get(pubkey)
                        if metadata is None:
                            await self._store.mark_identity_fetch_miss(
                                pubkey, attempted_at=attempted_at
                            )
                            missed_count += 1
                            continue
                        await self._store.update_identity_profile(
                            pubkey,
                            metadata,
                            fetched_at=attempted_at,
                        )
                        fetched_count += 1
                    logger.info(
                        "identity_indexer_fetch_cycle_complete",
                        extra={
                            "pubkey_count": len(pubkeys),
                            "fetched_count": fetched_count,
                            "missed_count": missed_count,
                            "relay_count": len(self._relays),
                        },
                    )
                else:
                    logger.info(
                        "identity_indexer_poll",
                        extra={"pubkey_count": 0},
                    )
                await stop_aware_sleep(stop_event, self._poll_interval_s)
        except asyncio.CancelledError:
            raise
        finally:
            logger.info("identity_indexer_stopped")
