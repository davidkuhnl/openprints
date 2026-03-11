"""Run the OpenPrints HTTP API (FastAPI + uvicorn)."""

from __future__ import annotations

import logging
import os

from openprints.common.settings import CliOverrides, build_runtime_settings
from openprints.common.utils.logging import configure_logging
from openprints.common.utils.output import print_json


def run_serve(args) -> int:
    """Start the API server. Config and port from args/env.
    Uses API logging settings (OPENPRINTS_API_LOG_* and OPENPRINTS_LOG_FORMAT)."""
    cli = CliOverrides(
        config_path=getattr(args, "config", None),
        port=getattr(args, "port", None),
        host=getattr(args, "host", None),
        log_level=getattr(args, "log_level", None),
    )
    settings, errors, _ = build_runtime_settings(config_path=getattr(args, "config", None), cli=cli)
    if errors:
        print_json({"ok": False, "errors": errors})
        return 1
    if settings is None:
        print_json({"ok": False, "errors": [{"message": "failed to load settings"}]})
        return 1

    os.environ["OPENPRINTS_LOG_LEVEL"] = settings.api_log_level
    if settings.api_log_folder and settings.api_log_base_name:
        os.environ["OPENPRINTS_LOG_FOLDER"] = settings.api_log_folder
        os.environ["OPENPRINTS_LOG_BASE_NAME"] = settings.api_log_base_name
    else:
        os.environ.pop("OPENPRINTS_LOG_FOLDER", None)
        os.environ.pop("OPENPRINTS_LOG_BASE_NAME", None)
    configure_logging()

    # Route uvicorn loggers through our root handler (no duplicate format)
    for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        _log = logging.getLogger(_name)
        _log.handlers.clear()
        _log.propagate = True

    port = settings.api_port
    if port < 1 or port > 65535:
        err = "Invalid port. Use config api_port, OPENPRINTS_API_PORT, or --port (1-65535)."
        print_json({"ok": False, "error": err})
        return 1

    # Incremental config so uvicorn.run doesn't replace our root setup
    _uvicorn_log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "incremental": True,
        "loggers": {
            "uvicorn": {"level": settings.api_log_level, "propagate": True},
            "uvicorn.error": {"level": settings.api_log_level, "propagate": True},
            "uvicorn.access": {"level": settings.api_log_level, "propagate": True},
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
