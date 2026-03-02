"""Tests for openprints db wipe command."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from argparse import Namespace
from pathlib import Path

from openprints.cli.commands.db import run_db_wipe


def test_db_wipe_requires_force(capsys) -> None:
    """Without --force, wipe exits with error even when database_path is set."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "openprints.db"
        config_path = Path(tmp) / "config.toml"
        config_path.write_text(f'[database]\ndatabase_path = "{db_path}"\n')
        args = Namespace(config=str(config_path), force=False)
        code = run_db_wipe(args)
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out.get("ok") is False
        assert "force" in out.get("error", "").lower()


def test_db_wipe_no_database_configured(capsys) -> None:
    """When no database_path is set, wipe exits with error."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(b'[indexer]\nrelays = ["ws://localhost:7447"]\n')
        config_path = f.name
    try:
        args = Namespace(config=config_path, force=True)
        code = run_db_wipe(args)
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out.get("ok") is False
        assert "no database path" in out.get("error", "").lower()
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_db_wipe_clears_tables_without_deleting_file(capsys) -> None:
    """With --force and database_path set, wipe clears rows and keeps DB file."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "openprints.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE design_versions (
                event_id TEXT PRIMARY KEY
            );
            CREATE TABLE designs (
                pubkey TEXT NOT NULL,
                design_id TEXT NOT NULL,
                latest_event_id TEXT NOT NULL,
                PRIMARY KEY (pubkey, design_id),
                FOREIGN KEY (latest_event_id) REFERENCES design_versions(event_id)
            );
            CREATE TABLE identities (
                pubkey TEXT PRIMARY KEY
            );
            INSERT INTO design_versions (event_id) VALUES ('evt1');
            INSERT INTO designs (pubkey, design_id, latest_event_id)
            VALUES ('pk1', 'openprints:abc', 'evt1');
            INSERT INTO identities (pubkey) VALUES ('pk1');
            """
        )
        conn.commit()
        conn.close()
        config_path = Path(tmp) / "config.toml"
        config_path.write_text(f'[database]\ndatabase_path = "{db_path}"\n')

        args = Namespace(config=str(config_path), force=True)
        code = run_db_wipe(args)
        assert code == 0
        assert db_path.exists()

        conn = sqlite3.connect(db_path)
        designs_count = conn.execute("SELECT COUNT(*) FROM designs").fetchone()[0]
        versions_count = conn.execute("SELECT COUNT(*) FROM design_versions").fetchone()[0]
        identities_count = conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0]
        conn.close()
        assert designs_count == 0
        assert versions_count == 0
        assert identities_count == 0

        out = json.loads(capsys.readouterr().out)
        assert out.get("ok") is True
        assert "wiped" in out
        assert out.get("rows_deleted", {}).get("designs") == 1
        assert out.get("rows_deleted", {}).get("design_versions") == 1
        assert out.get("rows_deleted", {}).get("identities") == 1
