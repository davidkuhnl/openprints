"""Health and readiness endpoints (same contract as indexer health server)."""

from __future__ import annotations

from fastapi import APIRouter, Response

from openprints.api.deps import get_ready_context
from openprints.indexer.health_checks import check_db, check_relays

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness: 200 if this HTTP process is up.
    Does not check indexer worker, DB, or relays; use GET /ready for that."""
    return {
        "status": "ok",
        "service": "openprints-api",
        "liveness": True,
        "message": "Process is up. Use GET /ready for DB and relay readiness.",
    }


def _ready_checks(db_path: str | None, relay_urls: list[str]) -> dict[str, str]:
    """Run readiness checks; return dict with keys database, relays.
    Values: 'ok', 'not_configured', or error string."""
    db_result: str
    if db_path:
        err = check_db(db_path)
        db_result = "ok" if err is None else err
    else:
        db_result = "not_configured"
    relay_result: str
    if relay_urls:
        err = check_relays(relay_urls)
        relay_result = "ok" if err is None else err
    else:
        relay_result = "not_configured"
    return {"database": db_result, "relays": relay_result}


@router.get("/ready")
def ready(response: Response) -> dict:
    """Readiness: 200 if all configured checks pass; else 503.

    Response always includes checks.database and checks.relays with explicit state:
    'ok', 'not_configured', or the error message.
    """
    db_path, relay_urls = get_ready_context()
    checks = _ready_checks(db_path, relay_urls)
    failed = [k for k, v in checks.items() if v not in ("ok", "not_configured")]
    if failed:
        response.status_code = 503
        return {
            "status": "error",
            "ready": False,
            "checks": checks,
            "relay_count": len(relay_urls),
        }
    return {
        "status": "ok",
        "ready": True,
        "checks": checks,
        "relay_count": len(relay_urls),
    }
