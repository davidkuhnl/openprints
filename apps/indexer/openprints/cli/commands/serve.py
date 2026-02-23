"""Run the OpenPrints HTTP API (FastAPI + uvicorn)."""

from __future__ import annotations

import logging
import os

from openprints.common.utils.logging import configure_logging
from openprints.indexer.config import load_indexer_config


def run_serve(args) -> int:
    """Start the API server. Config and port from args/env.
    Uses project logging (OPENPRINTS_LOG_LEVEL, OPENPRINTS_LOG_FORMAT)."""
    if getattr(args, "config", None):
        os.environ["OPENPRINTS_INDEXER_CONFIG"] = args.config

    # Use --log-level for OPENPRINTS_LOG_LEVEL so configure_logging picks it up
    log_level_arg = getattr(args, "log_level", None)
    if log_level_arg:
        os.environ["OPENPRINTS_LOG_LEVEL"] = log_level_arg.upper()

    configure_logging()

    # Route uvicorn loggers through our root handler (no duplicate format)
    for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        _log = logging.getLogger(_name)
        _log.handlers.clear()
        _log.propagate = True

    port = _resolve_port(args)
    if port is None or port < 1 or port > 65535:
        from openprints.common.utils.output import print_json

        err = "Invalid port. Use config api_port, OPENPRINTS_API_PORT, or --port (1-65535)."
        print_json({"ok": False, "error": err})
        return 1

    # Incremental config so uvicorn.run doesn't replace our root setup
    level_name = os.environ.get("OPENPRINTS_LOG_LEVEL", "INFO").upper()
    _uvicorn_log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "incremental": True,
        "loggers": {
            "uvicorn": {"level": level_name, "propagate": True},
            "uvicorn.error": {"level": level_name, "propagate": True},
            "uvicorn.access": {"level": level_name, "propagate": True},
        },
    }

    import uvicorn

    uvicorn.run(
        "openprints.api:app",
        host=getattr(args, "host", "0.0.0.0"),
        port=port,
        log_config=_uvicorn_log_config,
    )
    return 0  # unreachable if run blocks until shutdown


def _resolve_port(args) -> int | None:
    raw = getattr(args, "port", None)
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    raw = os.environ.get("OPENPRINTS_API_PORT", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            return None
    config, _errors, _path = load_indexer_config(None)
    raw = config.get("api_port")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return 8080
