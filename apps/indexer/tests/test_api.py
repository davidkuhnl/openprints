"""Minimal tests for openprints.api (FastAPI app)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from openprints.api import app
from openprints.api.routes import designs as designs_route
from openprints.common.design_id import api_id_encode
from openprints.common.identity_utils import truncate_middle
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
    assert identity["npub"].startswith("npub1")
    assert identity["display_name_resolved"] == "Alice"
    assert identity["name"] == "alice"
    assert identity["display_name"] == "Alice"
    assert identity["nip05"] == "alice@example.com"


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
