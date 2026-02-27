"""Tests for openprints db wipe command."""

from __future__ import annotations

import json
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


def test_db_wipe_deletes_file(capsys) -> None:
    """With --force and database_path set, wipe deletes the database file."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "openprints.db"
        db_path.touch()
        config_path = Path(tmp) / "config.toml"
        config_path.write_text(f'[database]\ndatabase_path = "{db_path}"\n')

        args = Namespace(config=str(config_path), force=True)
        code = run_db_wipe(args)
        assert code == 0
        assert not db_path.exists()

        out = json.loads(capsys.readouterr().out)
        assert out.get("ok") is True
        assert "wiped" in out
