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
from openprints.indexer.store import LogOnlyIndexStore
from openprints.indexer.store_sqlite import SQLiteIndexStore

logger = logging.getLogger(__name__)


def run_index(args: Namespace) -> int:
    cli = CliOverrides(
        config_path=getattr(args, "config", None),
        relay=getattr(args, "relay", None),
        kind=getattr(args, "kind", None),
        queue_maxsize=getattr(args, "queue_maxsize", None),
        timeout=getattr(args, "timeout", None),
        max_retries=getattr(args, "max_retries", None),
        duration=getattr(args, "duration", None),
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

    if settings.max_retries < 0:
        print_json(
            {"ok": False, "errors": [invalid_value("max_retries", "max_retries must be >= 0")]}
        )
        return 1
    if settings.duration < 0:
        print_json({"ok": False, "errors": [invalid_value("duration", "duration must be >= 0")]})
        return 1

    os.environ["OPENPRINTS_LOG_LEVEL"] = settings.log_level
    configure_logging()

    database_path = settings.database_path
    relay_urls = list(settings.relay_urls)
    store: LogOnlyIndexStore | SQLiteIndexStore
    if database_path:
        store = SQLiteIndexStore(database_path)
    else:
        store = LogOnlyIndexStore()

    async def _run() -> tuple[int, int, int]:
        if isinstance(store, SQLiteIndexStore):
            await store.open()
        try:
            design_indexer = DesignIndexer(
                relays=relay_urls,
                kind=settings.kind,
                timeout_s=settings.timeout,
                queue_maxsize=settings.queue_maxsize,
                max_retries=settings.max_retries,
                store=store,
            )
            app = IndexerApp(design_indexer=design_indexer)
            logger.info(
                "indexer_command_start",
                extra={
                    "relay_count": len(relay_urls),
                    "kind": settings.kind,
                    "queue_maxsize": settings.queue_maxsize,
                    "max_retries": settings.max_retries,
                    "timeout_s": settings.timeout,
                    "duration_s": settings.duration,
                    "config_source": config_source or "none",
                    "log_level": settings.log_level,
                    "database": database_path or "log",
                },
            )
            try:
                if settings.duration > 0:
                    await app.run_for(settings.duration)
                else:
                    await app.run_until_cancelled()
            except KeyboardInterrupt:
                await app.stop()
            return (
                design_indexer.reducer.stats.processed,
                design_indexer.reducer.stats.reduced,
                design_indexer.reducer.stats.duplicates,
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
