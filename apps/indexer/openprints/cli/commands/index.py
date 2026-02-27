from __future__ import annotations

import asyncio
import logging
import os
from argparse import Namespace

from openprints.common.config import load_app_config, resolve_database_path
from openprints.common.errors import invalid_value
from openprints.common.utils.logging import configure_logging
from openprints.common.utils.output import print_json
from openprints.common.utils.relay import resolve_relay_urls
from openprints.indexer.coordinator import IndexerCoordinator
from openprints.indexer.store import LogOnlyIndexStore
from openprints.indexer.store_sqlite import SQLiteIndexStore

logger = logging.getLogger(__name__)


def run_index(args: Namespace) -> int:
    config, config_errors, config_source = load_app_config(args.config)
    if config_errors:
        print_json({"ok": False, "errors": config_errors})
        return 1
    if config is None:
        return 1

    configured_relays = config.indexer.relays if config.indexer.relays else None
    relay_urls, relay_errors = resolve_relay_urls(
        args.relay,
        configured_relays=configured_relays,
    )
    if relay_errors:
        print_json({"ok": False, "errors": relay_errors})
        return 1

    kind, kind_errors = _resolve_int_option(
        args_value=args.kind,
        env_name="OPENPRINTS_INDEX_KIND",
        config_value=config.indexer.kind,
        default_value=33301,
        path="kind",
    )
    if kind_errors:
        print_json({"ok": False, "errors": kind_errors})
        return 1

    queue_maxsize, queue_errors = _resolve_int_option(
        args_value=args.queue_maxsize,
        env_name="OPENPRINTS_INDEX_QUEUE_MAXSIZE",
        config_value=config.indexer.queue_maxsize,
        default_value=1000,
        path="queue_maxsize",
    )
    if queue_errors:
        print_json({"ok": False, "errors": queue_errors})
        return 1

    timeout_s, timeout_errors = _resolve_float_option(
        args_value=args.timeout,
        env_name="OPENPRINTS_INDEX_TIMEOUT",
        config_value=config.indexer.timeout,
        default_value=8.0,
        path="timeout",
    )
    if timeout_errors:
        print_json({"ok": False, "errors": timeout_errors})
        return 1

    max_retries, retry_errors = _resolve_int_option(
        args_value=args.max_retries,
        env_name="OPENPRINTS_INDEX_MAX_RETRIES",
        config_value=config.indexer.max_retries,
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
        config_value=config.indexer.duration,
        default_value=0.0,
        path="duration",
    )
    if duration_errors:
        print_json({"ok": False, "errors": duration_errors})
        return 1
    if duration_s < 0:
        print_json({"ok": False, "errors": [invalid_value("duration", "duration must be >= 0")]})
        return 1

    if not os.environ.get("OPENPRINTS_LOG_LEVEL"):
        os.environ["OPENPRINTS_LOG_LEVEL"] = config.indexer.log_level

    configure_logging()

    database_path = resolve_database_path(config)
    store: LogOnlyIndexStore | SQLiteIndexStore
    if database_path:
        store = SQLiteIndexStore(database_path)
    else:
        store = LogOnlyIndexStore()

    async def _run() -> tuple[int, int, int]:
        if isinstance(store, SQLiteIndexStore):
            await store.open()
        try:
            coordinator = IndexerCoordinator(
                relays=relay_urls,
                kind=kind,
                timeout_s=timeout_s,
                queue_maxsize=queue_maxsize,
                max_retries=max_retries,
                store=store,
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
                    "database": database_path or "log",
                },
            )
            try:
                if duration_s > 0:
                    await coordinator.run_for(duration_s)
                else:
                    await coordinator.run_until_cancelled()
            except KeyboardInterrupt:
                pass
            return (
                coordinator.reducer.stats.processed,
                coordinator.reducer.stats.reduced,
                coordinator.reducer.stats.duplicates,
            )
        finally:
            if isinstance(store, SQLiteIndexStore):
                await store.close()

    try:
        processed, reduced, duplicates = asyncio.run(_run())
    except KeyboardInterrupt:
        processed, reduced, duplicates = 0, 0, 0

    print_json(
        {
            "ok": True,
            "relays": relay_urls,
            "stats": {"processed": processed, "reduced": reduced, "duplicates": duplicates},
        }
    )
    return 0


def _resolve_int_option(
    *,
    args_value: int | None,
    env_name: str,
    config_value: int,
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

    return config_value if config_value is not None else default_value, []


def _resolve_float_option(
    *,
    args_value: float | None,
    env_name: str,
    config_value: float,
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

    return float(config_value) if config_value is not None else default_value, []
