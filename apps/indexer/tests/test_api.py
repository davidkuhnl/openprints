"""Minimal tests for openprints.api (FastAPI app)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from openprints.api import app

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
