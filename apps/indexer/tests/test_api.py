"""Minimal tests for openprints.api (FastAPI app)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from openprints.api import app
from openprints.api.routes import designs as designs_route
from openprints.api.routes import identity as identity_route
from openprints.common.design_id import api_id_encode
from openprints.common.identity_utils import identity_api_id_from_pubkey, truncate_middle
from openprints.indexer.store import DesignCurrentRow

client = TestClient(app)


def test_health_returns_200_and_liveness() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "openprints-api"
    assert data.get("liveness") is True
    assert "ready" in (data.get("message") or "").lower()


def test_ready_returns_200_when_no_db_configured() -> None:
    """When no database_path is set, /ready passes (no DB to check)."""
    r = client.get("/ready")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("ready") is True
    assert "checks" in data
    assert data["checks"]["database"] == "not_configured"
    assert data["checks"]["relays"] == "not_configured"


def test_designs_returns_503_when_no_store() -> None:
    """When DB is not configured, GET /designs returns 503."""
    r = client.get("/designs")
    assert r.status_code == 503
    assert "not configured" in (r.json().get("detail") or "").lower()


def test_designs_stats_returns_503_when_no_store() -> None:
    """When DB is not configured, GET /designs/stats returns 503."""
    r = client.get("/designs/stats")
    assert r.status_code == 503
    assert "not configured" in (r.json().get("detail") or "").lower()


def test_designs_stats_filter_by_identity_id_npub(monkeypatch) -> None:
    pubkey = "b" * 64

    class _FakeStore:
        async def get_counts(self, **kwargs):
            # identity_id should be decoded to the underlying pubkey
            assert kwargs.get("creator_pubkey") == pubkey
            return 5, 10

    monkeypatch.setattr(designs_route, "get_store", lambda: _FakeStore())
    identity_id = identity_api_id_from_pubkey(pubkey)
    assert identity_id is not None
    r = client.get(f"/designs/stats?identity_id={identity_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["designs"] == 5
    assert data["versions"] == 10


def test_designs_stats_filter_by_identity_id_invalid_returns_400(monkeypatch) -> None:
    class _FakeStore:
        async def get_counts(self, **kwargs):
            raise AssertionError("get_counts should not be called for invalid identity_id")

    monkeypatch.setattr(designs_route, "get_store", lambda: _FakeStore())
    r = client.get("/designs/stats?identity_id=not-a-valid-identity-id")
    assert r.status_code == 400
    assert "invalid" in (r.json().get("detail") or "").lower()


def test_design_by_id_invalid_returns_400() -> None:
    r = client.get("/designs/not-valid-base64-id")
    assert r.status_code == 400
    assert "invalid" in (r.json().get("detail") or "").lower()


def test_openapi_schema_available() -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "openapi" in schema
    assert "paths" in schema
    assert "/health" in schema["paths"]
    assert "/designs" in schema["paths"]


def _sample_design_row(pubkey: str = "b" * 64) -> DesignCurrentRow:
    return DesignCurrentRow(
        pubkey=pubkey,
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


def test_designs_includes_creator_identity_with_resolved_name(monkeypatch) -> None:
    row = _sample_design_row()

    class _FakeStore:
        async def list_designs(self, **kwargs):
            return [row], 1

        async def get_identities_by_pubkeys(self, pubkeys):
            assert pubkeys == [row.pubkey]
            return {
                row.pubkey: {
                    "pubkey": row.pubkey,
                    "status": "fetched",
                    "pubkey_first_seen_at": 100,
                    "pubkey_last_seen_at": 200,
                    "name": "alice",
                    "display_name": "Alice",
                    "about": "maker",
                    "picture": "https://example.invalid/pic.png",
                    "banner": None,
                    "website": None,
                    "nip05": "alice@example.com",
                    "lud06": None,
                    "lud16": "alice@getalby.com",
                    "profile_raw_json": '{"name":"alice"}',
                    "profile_fetched_at": 300,
                    "fetch_last_attempt_at": 300,
                    "retry_count": 0,
                }
            }

    monkeypatch.setattr(designs_route, "get_store", lambda: _FakeStore())
    r = client.get("/designs")
    assert r.status_code == 200
    item = r.json()["items"][0]
    identity = item["creator_identity"]
    assert identity["pubkey"] == row.pubkey
    assert identity["id"] == identity_api_id_from_pubkey(row.pubkey)
    assert identity["npub"].startswith("npub1")
    assert identity["display_name_resolved"] == "Alice"
    assert identity["name"] == "alice"
    assert identity["display_name"] == "Alice"
    assert identity["nip05"] == "alice@example.com"


def test_designs_filter_by_identity_id_npub(monkeypatch) -> None:
    row = _sample_design_row()

    class _FakeStore:
        async def list_designs(self, **kwargs):
            # identity_id should be decoded to the underlying pubkey and passed as creator_pubkey
            assert kwargs.get("creator_pubkey") == row.pubkey
            return [row], 1

        async def get_identities_by_pubkeys(self, pubkeys):
            assert pubkeys == [row.pubkey]
            return {
                row.pubkey: {
                    "pubkey": row.pubkey,
                    "status": "fetched",
                    "pubkey_first_seen_at": 100,
                    "pubkey_last_seen_at": 200,
                    "name": "alice",
                    "display_name": "Alice",
                    "about": "maker",
                    "picture": "https://example.invalid/pic.png",
                    "banner": None,
                    "website": None,
                    "nip05": "alice@example.com",
                    "lud06": None,
                    "lud16": "alice@getalby.com",
                    "profile_raw_json": '{"name":"alice"}',
                    "profile_fetched_at": 300,
                    "fetch_last_attempt_at": 300,
                    "retry_count": 0,
                }
            }

    monkeypatch.setattr(designs_route, "get_store", lambda: _FakeStore())
    identity_id = identity_api_id_from_pubkey(row.pubkey)
    assert identity_id is not None
    r = client.get(f"/designs?identity_id={identity_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_designs_filter_by_identity_id_invalid_returns_400(monkeypatch) -> None:
    class _FakeStore:
        # Should not be called when identity_id is invalid
        async def list_designs(self, **kwargs):
            raise AssertionError("list_designs should not be called for invalid identity_id")

    monkeypatch.setattr(designs_route, "get_store", lambda: _FakeStore())
    r = client.get("/designs?identity_id=not-a-valid-identity-id")
    assert r.status_code == 400
    assert "invalid" in (r.json().get("detail") or "").lower()


def test_design_by_id_includes_creator_identity_fallback_to_truncated_npub(monkeypatch) -> None:
    row = _sample_design_row(pubkey="d" * 64)

    class _FakeStore:
        async def get_design(self, pubkey, design_id):
            assert (pubkey, design_id) == (row.pubkey, row.design_id)
            return row

        async def get_identities_by_pubkeys(self, pubkeys):
            assert pubkeys == [row.pubkey]
            return {
                row.pubkey: {
                    "pubkey": row.pubkey,
                    "status": "pending",
                    "pubkey_first_seen_at": 100,
                    "pubkey_last_seen_at": 200,
                    "name": "",
                    "display_name": "   ",
                    "about": None,
                    "picture": None,
                    "banner": None,
                    "website": None,
                    "nip05": "",
                    "lud06": None,
                    "lud16": None,
                    "profile_raw_json": None,
                    "profile_fetched_at": None,
                    "fetch_last_attempt_at": None,
                    "retry_count": 0,
                }
            }

    monkeypatch.setattr(designs_route, "get_store", lambda: _FakeStore())
    design_api_id = api_id_encode(row.pubkey, row.design_id)
    r = client.get(f"/designs/{design_api_id}")
    assert r.status_code == 200
    identity = r.json()["creator_identity"]
    npub = identity["npub"]
    assert isinstance(npub, str) and npub.startswith("npub1")
    assert identity["display_name_resolved"] == truncate_middle(npub)
    assert identity["id"] == identity_api_id_from_pubkey(row.pubkey)


def test_identity_by_id_invalid_returns_400() -> None:
    r = client.get("/identity/not-valid-identity-id")
    assert r.status_code == 400
    assert "invalid" in (r.json().get("detail") or "").lower()


def test_identity_by_id_not_found_returns_404(monkeypatch) -> None:
    pubkey = "e" * 64
    identity_id = identity_api_id_from_pubkey(pubkey)
    assert identity_id is not None

    class _FakeStore:
        async def get_identities_by_pubkeys(self, pubkeys):
            assert pubkeys == [pubkey]
            return {}

    monkeypatch.setattr(identity_route, "get_store", lambda: _FakeStore())
    r = client.get(f"/identity/{identity_id}")
    assert r.status_code == 404
    assert "not found" in (r.json().get("detail") or "").lower()


def test_identity_by_id_returns_full_identity(monkeypatch) -> None:
    pubkey = "f" * 64
    identity_id = identity_api_id_from_pubkey(pubkey)
    assert identity_id is not None

    class _FakeStore:
        async def get_identities_by_pubkeys(self, pubkeys):
            assert pubkeys == [pubkey]
            return {
                pubkey: {
                    "pubkey": pubkey,
                    "status": "fetched",
                    "pubkey_first_seen_at": 100,
                    "pubkey_last_seen_at": 200,
                    "name": "alice",
                    "display_name": "Alice",
                    "about": "maker",
                    "picture": "https://example.invalid/pic.png",
                    "banner": "https://example.invalid/banner.png",
                    "website": "https://example.invalid",
                    "nip05": "alice@example.com",
                    "lud06": "lnurl1example",
                    "lud16": "alice@getalby.com",
                    "profile_raw_json": '{"name":"alice"}',
                    "profile_fetched_at": 300,
                    "fetch_last_attempt_at": 300,
                    "retry_count": 0,
                }
            }

    monkeypatch.setattr(identity_route, "get_store", lambda: _FakeStore())
    r = client.get(f"/identity/{identity_id}")
    assert r.status_code == 200
    payload = r.json()
    assert payload["id"] == identity_id
    assert payload["pubkey"] == pubkey
    assert payload["npub"].startswith("npub1")
    assert payload["display_name_resolved"] == "Alice"
    assert payload["name"] == "alice"
    assert payload["display_name"] == "Alice"
    assert payload["about"] == "maker"
    assert payload["nip05"] == "alice@example.com"
