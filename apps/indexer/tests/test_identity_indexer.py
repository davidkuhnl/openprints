from __future__ import annotations

import asyncio

import openprints.indexer.identity_indexer as identity_mod
from openprints.indexer.identity_indexer import IdentityIndexer


class _FakeIdentityStore:
    def __init__(self) -> None:
        self.calls = 0
        self.updated: list[str] = []
        self.missed: list[str] = []

    async def list_identity_pubkeys_for_refresh(
        self, *, limit: int, stale_after_s: int, now_ts: int
    ) -> list[str]:
        self.calls += 1
        if self.calls == 1:
            return ["a" * 64, "b" * 64]
        return []

    async def update_identity_profile(
        self, pubkey: str, metadata: dict[str, str | None], *, fetched_at: int
    ) -> None:
        self.updated.append(pubkey)

    async def mark_identity_fetch_miss(self, pubkey: str, *, attempted_at: int) -> None:
        self.missed.append(pubkey)


def test_identity_indexer_fetches_and_marks_misses(monkeypatch) -> None:
    async def _fake_fetch_kind0_for_pubkeys(pubkeys, relays, *, timeout_s):
        assert pubkeys == ["a" * 64, "b" * 64]
        assert relays == ["ws://localhost:7447"]
        assert timeout_s == 2.0
        return {
            "a" * 64: {
                "name": "alice",
                "display_name": None,
                "about": None,
                "picture": None,
                "shape": "⭐",
                "banner": None,
                "website": None,
                "nip05": None,
                "lud06": None,
                "lud16": None,
                "profile_raw_json": '{"name":"alice"}',
            }
        }

    monkeypatch.setattr(identity_mod, "fetch_kind0_for_pubkeys", _fake_fetch_kind0_for_pubkeys)
    store = _FakeIdentityStore()
    indexer = IdentityIndexer(
        store=store,
        relays=["ws://localhost:7447"],
        batch_size=10,
        stale_after_s=60,
        poll_interval_s=0.05,
        fetch_timeout_s=2.0,
    )

    async def _run() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(indexer.run(stop_event))
        await asyncio.sleep(0.12)
        stop_event.set()
        await task

    asyncio.run(_run())
    assert store.calls >= 1
    assert store.updated == ["a" * 64]
    assert store.missed == ["b" * 64]
