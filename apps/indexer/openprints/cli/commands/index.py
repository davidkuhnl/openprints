from __future__ import annotations

import asyncio
import logging
import os
from argparse import Namespace

from openprints.common.errors import invalid_value
from openprints.common.settings import CliOverrides, build_runtime_settings
from openprints.common.utils.logging import configure_logging
from openprints.common.utils.output import print_json
from openprints.indexer.app import IndexerApp
from openprints.indexer.design_indexer import DesignIndexer
from openprints.indexer.identity_indexer import IdentityIndexer
from openprints.indexer.store import LogOnlyIndexStore
from openprints.indexer.store_sqlite import SQLiteIndexStore

logger = logging.getLogger(__name__)


def run_index(args: Namespace) -> int:
    cli = CliOverrides(
        config_path=getattr(args, "config", None),
        relay=getattr(args, "relay", None),
        design_kind=getattr(args, "design_kind", None),
        design_queue_maxsize=getattr(args, "design_queue_maxsize", None),
        design_timeout_s=getattr(args, "design_timeout_s", None),
        design_max_retries=getattr(args, "design_max_retries", None),
        design_duration_s=getattr(args, "design_duration_s", None),
        log_level=getattr(args, "log_level", None),
    )
    settings, errors, config_source = build_runtime_settings(
        config_path=getattr(args, "config", None), cli=cli
    )
    if errors:
        print_json({"ok": False, "errors": errors})
        return 1
    if settings is None:
        print_json({"ok": False, "errors": [{"message": "failed to build runtime settings"}]})
        return 1

    if settings.design_max_retries < 0:
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("design_max_retries", "design_max_retries must be >= 0")],
            }
        )
        return 1
    if settings.design_duration_s < 0:
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("design_duration_s", "design_duration_s must be >= 0")],
            }
        )
        return 1

    os.environ["OPENPRINTS_LOG_LEVEL"] = settings.log_level
    if settings.log_folder and settings.log_base_name:
        os.environ["OPENPRINTS_LOG_FOLDER"] = settings.log_folder
        os.environ["OPENPRINTS_LOG_BASE_NAME"] = settings.log_base_name
    else:
        os.environ.pop("OPENPRINTS_LOG_FOLDER", None)
        os.environ.pop("OPENPRINTS_LOG_BASE_NAME", None)
    configure_logging()

    database_path = settings.database_path
    relay_urls = list(settings.relay_urls)
    store: LogOnlyIndexStore | SQLiteIndexStore
    if database_path:
        store = SQLiteIndexStore(database_path)
    else:
        store = LogOnlyIndexStore()

    # So we can report real stats when Ctrl+C hits (outer except would otherwise get no return).
    stats_ref: dict[str, int] = {"processed": 0, "reduced": 0, "duplicates": 0}
    design_indexer: DesignIndexer | None = None

    async def _run() -> tuple[int, int, int]:
        nonlocal design_indexer
        if isinstance(store, SQLiteIndexStore):
            await store.open()
        try:
            design_indexer = DesignIndexer(
                relays=relay_urls,
                kind=settings.design_kind,
                timeout_s=settings.design_timeout_s,
                queue_maxsize=settings.design_queue_maxsize,
                max_retries=settings.design_max_retries,
                store=store,
            )
            identity_indexer = IdentityIndexer(
                store=store,
                relays=relay_urls,
                batch_size=settings.identity_batch_size,
                stale_after_s=settings.identity_stale_after_s,
                poll_interval_s=settings.identity_poll_interval_s,
                fetch_timeout_s=settings.identity_fetch_timeout_s,
            )
            app = IndexerApp(design_indexer=design_indexer, identity_indexer=identity_indexer)
            logger.info(
                "indexer_command_start",
                extra={
                    "relay_count": len(relay_urls),
                    "design_kind": settings.design_kind,
                    "design_queue_maxsize": settings.design_queue_maxsize,
                    "design_max_retries": settings.design_max_retries,
                    "design_timeout_s": settings.design_timeout_s,
                    "design_duration_s": settings.design_duration_s,
                    "config_source": config_source or "none",
                    "log_level": settings.log_level,
                    "database": database_path or "log",
                    "identity_batch_size": settings.identity_batch_size,
                    "identity_stale_after_s": settings.identity_stale_after_s,
                    "identity_poll_interval_s": settings.identity_poll_interval_s,
                    "identity_fetch_timeout_s": settings.identity_fetch_timeout_s,
                },
            )
            try:
                if settings.design_duration_s > 0:
                    await app.run_for(settings.design_duration_s)
                else:
                    await app.run_until_cancelled()
            except KeyboardInterrupt:
                await app.stop()
                raise
            return (
                design_indexer.reducer.stats.processed,
                design_indexer.reducer.stats.reduced,
                design_indexer.reducer.stats.duplicates,
            )
        finally:
            if design_indexer is not None:
                stats_ref["processed"] = design_indexer.reducer.stats.processed
                stats_ref["reduced"] = design_indexer.reducer.stats.reduced
                stats_ref["duplicates"] = design_indexer.reducer.stats.duplicates
            if isinstance(store, SQLiteIndexStore):
                await store.close()

    try:
        processed, reduced, duplicates = asyncio.run(_run())
    except KeyboardInterrupt:
        processed = stats_ref["processed"]
        reduced = stats_ref["reduced"]
        duplicates = stats_ref["duplicates"]

    print_json(
        {
            "ok": True,
            "relays": relay_urls,
            "stats": {"processed": processed, "reduced": reduced, "duplicates": duplicates},
        }
    )
    return 0
