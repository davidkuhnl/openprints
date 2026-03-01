"""Database operations (e.g. stats, wipe)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from openprints.common.settings import build_runtime_settings
from openprints.common.utils.output import print_json


def run_db_stats(args) -> int:
    """Print indexer database stats and a short list of designs."""
    settings, errors, _ = build_runtime_settings(config_path=getattr(args, "config", None))
    if errors:
        print_json({"ok": False, "errors": errors})
        return 1
    if settings is None:
        print_json({"ok": False, "errors": [{"message": "failed to build runtime settings"}]})
        return 1

    database_path = settings.database_path
    if not database_path or database_path.strip().lower() == ":memory:":
        print_json({"ok": False, "error": "No database path configured; nothing to inspect."})
        return 1

    path = Path(database_path)
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        print_json({"ok": False, "error": f"Database file not found: {path}"})
        return 1

    limit = max(0, getattr(args, "limit", 10) or 0)
    return asyncio.run(_run_db_stats(path, limit))


async def _run_db_stats(path: Path, limit: int) -> int:
    async with aiosqlite.connect(str(path)) as conn:
        async with conn.execute("SELECT COUNT(*) FROM designs") as cur:
            (designs_count,) = await cur.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM design_versions") as cur:
            (versions_count,) = await cur.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM identities") as cur:
            (identities_count,) = await cur.fetchone()
        async with conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM identities
            GROUP BY status
            """
        ) as cur:
            identity_by_status = {row[0]: row[1] for row in await cur.fetchall()}
    pending = identity_by_status.get("pending", 0)
    fetched = identity_by_status.get("fetched", 0)
    failed = identity_by_status.get("failed", 0)

    print(f"Database: {path}")
    print(f"  designs:         {designs_count}")
    print(f"  design_versions: {versions_count}")
    print(
        f"  identities:      {identities_count} "
        f"(pending: {pending}, fetched: {fetched}, failed: {failed})"
    )

    if limit > 0 and designs_count > 0:
        async with aiosqlite.connect(str(path)) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                """
                SELECT pubkey, design_id, name, latest_published_at, version_count
                FROM designs
                ORDER BY latest_published_at DESC
                LIMIT ?
                """,
                (limit,),
            ) as cur:
                rows = await cur.fetchall()
        print(f"\nLatest {len(rows)} design(s):")
        for row in rows:
            pubkey = row["pubkey"] or ""
            if len(pubkey) > 16:
                pubkey_short = pubkey[:16] + "…"
            else:
                pubkey_short = pubkey

            raw_name = row["name"] or ""
            if len(raw_name) > 40:
                name = raw_name[:40] + "…"
            else:
                name = raw_name or "-"

            print(
                f"  {pubkey_short}  {row['design_id']}  {name}  "
                f"v{row['version_count']}  {row['latest_published_at']}"
            )

    return 0


def run_db_wipe(args) -> int:
    """Wipe the indexer SQLite database. Requires --force."""
    settings, errors, _ = build_runtime_settings(config_path=getattr(args, "config", None))
    if errors:
        print_json({"ok": False, "errors": errors})
        return 1
    if settings is None:
        print_json({"ok": False, "errors": [{"message": "failed to build runtime settings"}]})
        return 1

    database_path = settings.database_path
    if not database_path or database_path.strip().lower() == ":memory:":
        print_json({"ok": False, "error": "No database path configured; nothing to wipe."})
        return 1

    if not getattr(args, "force", False):
        print_json({"ok": False, "error": "Use --force to wipe the database."})
        return 1

    path = Path(database_path)
    if not path.is_absolute():
        path = Path.cwd() / path

    if path.exists():
        path.unlink()

    print_json({"ok": True, "wiped": str(path)})
    return 0
