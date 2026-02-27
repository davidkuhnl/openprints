"""Run the OpenPrints HTTP API (FastAPI + uvicorn)."""

from __future__ import annotations

import logging
import os

from openprints.common.settings import CliOverrides, build_runtime_settings
from openprints.common.utils.logging import configure_logging


def run_serve(args) -> int:
    """Start the API server. Config and port from args/env.
    Uses project logging (OPENPRINTS_LOG_LEVEL, OPENPRINTS_LOG_FORMAT)."""
    cli = CliOverrides(
        config_path=getattr(args, "config", None),
        port=getattr(args, "port", None),
        host=getattr(args, "host", None),
        log_level=getattr(args, "log_level", None),
    )
    settings, errors, _ = build_runtime_settings(config_path=getattr(args, "config", None), cli=cli)
    if errors:
        from openprints.common.utils.output import print_json

        print_json({"ok": False, "errors": errors})
        return 1
    if settings is None:
        from openprints.common.utils.output import print_json

        print_json({"ok": False, "errors": [{"message": "failed to load settings"}]})
        return 1

    os.environ["OPENPRINTS_LOG_LEVEL"] = settings.log_level
    configure_logging()

    # Route uvicorn loggers through our root handler (no duplicate format)
    for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        _log = logging.getLogger(_name)
        _log.handlers.clear()
        _log.propagate = True

    port = settings.api_port
    if port < 1 or port > 65535:
        from openprints.common.utils.output import print_json

        err = "Invalid port. Use config api_port, OPENPRINTS_API_PORT, or --port (1-65535)."
        print_json({"ok": False, "error": err})
        return 1

    # Incremental config so uvicorn.run doesn't replace our root setup
    _uvicorn_log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "incremental": True,
        "loggers": {
            "uvicorn": {"level": settings.log_level, "propagate": True},
            "uvicorn.error": {"level": settings.log_level, "propagate": True},
            "uvicorn.access": {"level": settings.log_level, "propagate": True},
        },
    }

    import uvicorn

    uvicorn.run(
        "openprints.api:app",
        host=settings.api_host,
        port=port,
        log_config=_uvicorn_log_config,
    )
    return 0  # unreachable if run blocks until shutdown
