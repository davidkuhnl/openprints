from __future__ import annotations

import asyncio
import logging
import os
from argparse import Namespace
from typing import Any

from openprints.common.errors import invalid_type, invalid_value
from openprints.common.utils.logging import configure_logging
from openprints.common.utils.output import print_json
from openprints.common.utils.relay import resolve_relay_urls
from openprints.indexer.config import load_indexer_config
from openprints.indexer.coordinator import IndexerCoordinator

logger = logging.getLogger(__name__)


def run_index(args: Namespace) -> int:
    config, config_errors, config_source = load_indexer_config(args.config)
    if config_errors:
        print_json({"ok": False, "errors": config_errors})
        return 1

    config_relays, config_relay_errors = _resolve_config_relays(config)
    if config_relay_errors:
        print_json({"ok": False, "errors": config_relay_errors})
        return 1

    relay_urls, relay_errors = resolve_relay_urls(
        args.relay,
        configured_relays=config_relays,
    )
    if relay_errors:
        print_json({"ok": False, "errors": relay_errors})
        return 1

    kind, kind_errors = _resolve_int_option(
        args_value=args.kind,
        env_name="OPENPRINTS_INDEX_KIND",
        config_value=config.get("kind"),
        default_value=33301,
        path="kind",
    )
    if kind_errors:
        print_json({"ok": False, "errors": kind_errors})
        return 1

    queue_maxsize, queue_errors = _resolve_int_option(
        args_value=args.queue_maxsize,
        env_name="OPENPRINTS_INDEX_QUEUE_MAXSIZE",
        config_value=config.get("queue_maxsize"),
        default_value=1000,
        path="queue_maxsize",
    )
    if queue_errors:
        print_json({"ok": False, "errors": queue_errors})
        return 1

    timeout_s, timeout_errors = _resolve_float_option(
        args_value=args.timeout,
        env_name="OPENPRINTS_INDEX_TIMEOUT",
        config_value=config.get("timeout"),
        default_value=8.0,
        path="timeout",
    )
    if timeout_errors:
        print_json({"ok": False, "errors": timeout_errors})
        return 1

    max_retries, retry_errors = _resolve_int_option(
        args_value=args.max_retries,
        env_name="OPENPRINTS_INDEX_MAX_RETRIES",
        config_value=config.get("max_retries"),
        default_value=12,
        path="max_retries",
    )
    if retry_errors:
        print_json({"ok": False, "errors": retry_errors})
        return 1
    if max_retries < 0:
        print_json(
            {"ok": False, "errors": [invalid_value("max_retries", "max_retries must be >= 0")]}
        )
        return 1

    duration_s, duration_errors = _resolve_float_option(
        args_value=args.duration,
        env_name="OPENPRINTS_INDEX_DURATION",
        config_value=config.get("duration"),
        default_value=0.0,
        path="duration",
    )
    if duration_errors:
        print_json({"ok": False, "errors": duration_errors})
        return 1
    if duration_s < 0:
        print_json({"ok": False, "errors": [invalid_value("duration", "duration must be >= 0")]})
        return 1

    config_log_level, log_level_errors = _resolve_config_log_level(config)
    if log_level_errors:
        print_json({"ok": False, "errors": log_level_errors})
        return 1
    if config_log_level and not os.environ.get("OPENPRINTS_LOG_LEVEL"):
        os.environ["OPENPRINTS_LOG_LEVEL"] = config_log_level

    configure_logging()

    coordinator = IndexerCoordinator(
        relays=relay_urls,
        kind=kind,
        timeout_s=timeout_s,
        queue_maxsize=queue_maxsize,
        max_retries=max_retries,
    )

    logger.info(
        "indexer_command_start",
        extra={
            "relay_count": len(relay_urls),
            "kind": kind,
            "queue_maxsize": queue_maxsize,
            "max_retries": max_retries,
            "timeout_s": timeout_s,
            "duration_s": duration_s,
            "config_source": config_source or "none",
            "log_level": os.environ.get("OPENPRINTS_LOG_LEVEL", "WARNING"),
        },
    )
    try:
        if duration_s > 0:
            asyncio.run(coordinator.run_for(duration_s))
        else:
            asyncio.run(coordinator.run_until_cancelled())
    except KeyboardInterrupt:
        pass

    print_json(
        {
            "ok": True,
            "relays": relay_urls,
            "stats": {
                "processed": coordinator.reducer.stats.processed,
                "reduced": coordinator.reducer.stats.reduced,
                "duplicates": coordinator.reducer.stats.duplicates,
            },
        }
    )
    return 0


def _resolve_config_relays(config: dict[str, Any]) -> tuple[list[str] | None, list[dict[str, str]]]:
    raw = config.get("relays")
    if isinstance(raw, list):
        values = [value for value in raw if isinstance(value, str) and value.strip()]
        if len(values) != len(raw):
            return None, [invalid_type("config.relays", "a list of relay URL strings")]
        return values or None, []
    if raw is not None:
        return None, [invalid_type("config.relays", "a list of relay URL strings")]

    single = config.get("relay")
    if isinstance(single, str) and single.strip():
        return [single.strip()], []
    if single is not None:
        return None, [invalid_type("config.relay", "a relay URL string")]

    return None, []


def _resolve_config_log_level(config: dict[str, Any]) -> tuple[str | None, list[dict[str, str]]]:
    raw = config.get("log_level")
    if raw is None:
        return None, []
    if not isinstance(raw, str):
        return None, [invalid_type("config.log_level", "a string")]

    value = raw.strip().upper()
    allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    if value not in allowed:
        return None, [
            invalid_value(
                "config.log_level",
                "log_level must be one of: CRITICAL, ERROR, WARNING, INFO, DEBUG",
            )
        ]
    return value, []


def _resolve_int_option(
    *,
    args_value: int | None,
    env_name: str,
    config_value: Any,
    default_value: int,
    path: str,
) -> tuple[int, list[dict[str, str]]]:
    if args_value is not None:
        return args_value, []

    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        try:
            return int(env_value), []
        except ValueError:
            return 0, [invalid_value(path, f"{path} env override must be an integer ({env_name})")]

    if config_value is not None:
        if isinstance(config_value, int):
            return config_value, []
        return 0, [invalid_type(f"config.{path}", "an integer")]

    return default_value, []


def _resolve_float_option(
    *,
    args_value: float | None,
    env_name: str,
    config_value: Any,
    default_value: float,
    path: str,
) -> tuple[float, list[dict[str, str]]]:
    if args_value is not None:
        return args_value, []

    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        try:
            return float(env_value), []
        except ValueError:
            return 0.0, [invalid_value(path, f"{path} env override must be a number ({env_name})")]

    if config_value is not None:
        if isinstance(config_value, (int, float)):
            return float(config_value), []
        return 0.0, [invalid_type(f"config.{path}", "a number")]

    return default_value, []
