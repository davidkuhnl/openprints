import asyncio

from openprints.indexer.reducer import ReducerWorker
from openprints.indexer.store import DesignCurrentRow, DesignVersionRow, LogOnlyIndexStore
from openprints.indexer.types import IngestEnvelope
from tests.test_helpers import valid_signed_payload


class _CapturingStore(LogOnlyIndexStore):
    def __init__(self) -> None:
        self.versions: list[DesignVersionRow] = []
        self.current_rows: list[DesignCurrentRow] = []
        self.identity_pending: list[tuple[str, int]] = []
        self._version_by_event_id: dict[str, DesignVersionRow] = {}
        self._current_by_key: dict[tuple[str, str], DesignCurrentRow] = {}

    async def append_design_version(self, row: DesignVersionRow) -> bool:
        if row.event_id in self._version_by_event_id:
            return False
        self._version_by_event_id[row.event_id] = row
        self.versions.append(row)
        return True

    async def upsert_design_current(self, row: DesignCurrentRow) -> None:
        self._current_by_key[(row.pubkey, row.design_id)] = row
        self.current_rows.append(row)

    async def get_design(self, pubkey: str, design_id: str) -> DesignCurrentRow | None:
        return self._current_by_key.get((pubkey, design_id))

    async def ensure_identity_pending(self, pubkey: str, first_seen_at: int) -> None:
        self.identity_pending.append((pubkey, first_seen_at))


def _envelope_for(
    event: dict, *, relay: str = "ws://localhost:7447", received_at: int = 1
) -> IngestEnvelope:
    return IngestEnvelope(relay=relay, received_at=received_at, event=event)


def test_reducer_creates_current_row_for_first_event() -> None:
    payload = valid_signed_payload()
    event = payload["event"]
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)

    asyncio.run(reducer.reduce_one(_envelope_for(event, received_at=100)))

    assert reducer.stats.reduced == 1
    assert len(store.versions) == 1
    assert len(store.current_rows) == 1
    current = store.current_rows[-1]
    assert current.version_count == 1
    assert current.latest_event_id == event["id"]
    assert current.first_published_at == event["created_at"]
    assert current.latest_published_at == event["created_at"]
    assert store.identity_pending == [(event["pubkey"], 100)]


def test_reducer_increments_version_count_and_updates_latest() -> None:
    payload = valid_signed_payload()
    event1 = dict(payload["event"])
    event2 = dict(payload["event"])
    event2["id"] = "f" * 64
    event2["created_at"] = event1["created_at"] + 10
    event2["content"] = "newer content"

    store = _CapturingStore()
    reducer = ReducerWorker(store=store)

    asyncio.run(reducer.reduce_one(_envelope_for(event1, received_at=100)))
    asyncio.run(reducer.reduce_one(_envelope_for(event2, received_at=110)))

    assert reducer.stats.reduced == 2
    current = store.current_rows[-1]
    assert current.version_count == 2
    assert current.first_published_at == event1["created_at"]
    assert current.latest_published_at == event2["created_at"]
    assert current.latest_event_id == event2["id"]
    assert current.content == "newer content"


def test_reducer_ignores_duplicate_event_ids() -> None:
    payload = valid_signed_payload()
    event = payload["event"]
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)

    asyncio.run(reducer.reduce_one(_envelope_for(event, received_at=100)))
    asyncio.run(reducer.reduce_one(_envelope_for(event, received_at=101)))

    assert reducer.stats.reduced == 1
    assert reducer.stats.duplicates == 1
    assert len(store.versions) == 1


def test_reducer_raises_for_event_without_id() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    del event["id"]
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    try:
        asyncio.run(reducer.reduce_one(_envelope_for(event)))
    except RuntimeError as exc:
        assert "id and pubkey must be strings" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing id")


def test_reducer_raises_for_event_without_pubkey() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    del event["pubkey"]
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    try:
        asyncio.run(reducer.reduce_one(_envelope_for(event)))
    except RuntimeError as exc:
        assert "id and pubkey must be strings" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing pubkey")


def test_reducer_raises_for_event_with_non_string_id() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["id"] = 12345
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    try:
        asyncio.run(reducer.reduce_one(_envelope_for(event)))
    except RuntimeError as exc:
        assert "id and pubkey must be strings" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for non-string id")


def test_reducer_ignores_event_without_d_tag() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["tags"] = [["name", "Only name"], ["format", "stl"]]
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    try:
        asyncio.run(reducer.reduce_one(_envelope_for(event)))
    except RuntimeError as exc:
        assert "design_id must be a valid openprints:uuid-v4" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing d tag")


def test_reducer_raises_for_event_with_non_openprints_d_tag() -> None:
    """Event with d tag that is not openprints:uuid-v4 causes invariant error."""
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["tags"] = [
        ["d", "openprints:abc"],
        ["name", "x"],
        ["format", "stl"],
        ["sha256", "0" * 64],
        ["url", "https://x"],
    ]
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    try:
        asyncio.run(reducer.reduce_one(_envelope_for(event)))
    except RuntimeError as exc:
        assert "design_id must be a valid openprints:uuid-v4" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for non-openprints d tag")


def test_reducer_raises_for_event_with_non_int_kind() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["kind"] = "33301"
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    try:
        asyncio.run(reducer.reduce_one(_envelope_for(event)))
    except RuntimeError as exc:
        assert "kind and created_at must be integers" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for non-int kind")


def test_reducer_raises_for_event_with_non_int_created_at() -> None:
    payload = valid_signed_payload()
    event = dict(payload["event"])
    event["created_at"] = "1730000000"
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    try:
        asyncio.run(reducer.reduce_one(_envelope_for(event)))
    except RuntimeError as exc:
        assert "kind and created_at must be integers" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for non-int created_at")


def test_reducer_keeps_older_event_when_created_at_tie_break() -> None:
    """When created_at is equal, higher event_id wins (lexicographic)."""
    payload = valid_signed_payload()
    event1 = dict(payload["event"])
    event2 = dict(payload["event"])
    event1["id"] = "a" * 64
    event1["created_at"] = 100
    event2["id"] = "b" * 64
    event2["created_at"] = 100
    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    asyncio.run(reducer.reduce_one(_envelope_for(event1, received_at=1)))
    asyncio.run(reducer.reduce_one(_envelope_for(event2, received_at=2)))
    assert reducer.stats.reduced == 2
    current = store.current_rows[-1]
    assert current.latest_event_id == "b" * 64
    assert current.version_count == 2


def test_reducer_persists_previous_version_event_id_from_tag() -> None:
    payload = valid_signed_payload()
    first_event = dict(payload["event"])
    second_event = dict(payload["event"])
    second_event["id"] = "f" * 64
    second_event["created_at"] = first_event["created_at"] + 10
    second_event["tags"] = [
        [entry[0], entry[1]]
        for entry in first_event["tags"]
        if isinstance(entry, list) and len(entry) >= 2
    ] + [["previous_version_event_id", first_event["id"]]]

    store = _CapturingStore()
    reducer = ReducerWorker(store=store)
    asyncio.run(reducer.reduce_one(_envelope_for(first_event, received_at=100)))
    asyncio.run(reducer.reduce_one(_envelope_for(second_event, received_at=110)))

    assert len(store.versions) == 2
    assert store.versions[0].previous_version_event_id is None
    assert store.versions[1].previous_version_event_id == first_event["id"]
