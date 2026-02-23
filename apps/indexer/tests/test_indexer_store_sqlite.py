"""Tests for openprints.indexer.store_sqlite."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import aiosqlite

from openprints.indexer.store import DesignCurrentRow, DesignVersionRow
from openprints.indexer.store_sqlite import SQLiteIndexStore


def _sample_version_row() -> DesignVersionRow:
    return DesignVersionRow(
        event_id="a" * 64,
        pubkey="b" * 64,
        design_id="openprints:00000000-0000-4000-8000-000000000001",
        kind=33301,
        created_at=1730000000,
        name="Test Design",
        format="stl",
        sha256="c" * 64,
        url="https://example.invalid/design.stl",
        content="Description",
        raw_event_json='{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',
        received_at=1730000100,
    )


def _sample_current_row() -> DesignCurrentRow:
    return DesignCurrentRow(
        pubkey="b" * 64,
        design_id="openprints:00000000-0000-4000-8000-000000000001",
        latest_event_id="a" * 64,
        latest_published_at=1730000000,
        first_published_at=1730000000,
        first_seen_at=1730000100,
        updated_at=1730000100,
        version_count=1,
        name="Test Design",
        format="stl",
        sha256="c" * 64,
        url="https://example.invalid/design.stl",
        content="Description",
        tags_json="{}",
    )


async def _run_upsert_and_read_back() -> None:
    store = SQLiteIndexStore(":memory:")
    await store.open()

    v = _sample_version_row()
    c = _sample_current_row()
    await store.upsert_design_version(v)
    await store.upsert_design_current(c)

    conn = store._conn
    assert conn is not None
    async with conn.execute("SELECT event_id, pubkey, design_id, name FROM design_versions") as cur:
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == v.event_id
    assert row[1] == v.pubkey
    assert row[2] == v.design_id
    assert row[3] == v.name

    async with conn.execute(
        "SELECT pubkey, design_id, latest_event_id, version_count FROM designs"
    ) as cur:
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == c.pubkey
    assert row[1] == c.design_id
    assert row[2] == c.latest_event_id
    assert row[3] == c.version_count

    await store.close()


def test_sqlite_store_upsert_and_read_back() -> None:
    asyncio.run(_run_upsert_and_read_back())


async def _run_persists_to_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.db"
        store = SQLiteIndexStore(path)
        await store.open()
        await store.upsert_design_version(_sample_version_row())
        await store.upsert_design_current(_sample_current_row())
        await store.close()

        assert path.exists()
        async with aiosqlite.connect(str(path)) as conn:
            async with conn.execute("SELECT COUNT(*) FROM design_versions") as cur:
                (n,) = await cur.fetchone()
            assert n == 1
            async with conn.execute("SELECT COUNT(*) FROM designs") as cur:
                (n,) = await cur.fetchone()
            assert n == 1


def test_sqlite_store_persists_to_file() -> None:
    asyncio.run(_run_persists_to_file())


def test_reducer_writes_to_sqlite_store() -> None:
    """Reducer with SQLiteIndexStore persists to design_versions and designs."""
    from openprints.indexer.reducer import ReducerWorker
    from openprints.indexer.types import IngestEnvelope
    from tests.test_helpers import valid_signed_payload

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.db"
        store = SQLiteIndexStore(path)
        asyncio.run(store.open())
        reducer = ReducerWorker(store=store)
        payload = valid_signed_payload()
        envelope = IngestEnvelope(
            relay="ws://localhost:7447",
            received_at=1730000100,
            event=payload["event"],
        )
        asyncio.run(reducer.reduce_one(envelope))
        asyncio.run(store.close())

        async def _check() -> None:
            async with aiosqlite.connect(str(path)) as conn:
                async with conn.execute("SELECT COUNT(*) FROM design_versions") as cur:
                    (n,) = await cur.fetchone()
                assert n == 1
                async with conn.execute("SELECT COUNT(*) FROM designs") as cur:
                    (n,) = await cur.fetchone()
                assert n == 1

        asyncio.run(_check())
