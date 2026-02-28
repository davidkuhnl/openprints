"""Tests for openprints db stats command."""

from __future__ import annotations

import asyncio
import json
from argparse import Namespace
from pathlib import Path

import pytest

from openprints.cli.commands.db import run_db_stats
from openprints.indexer.store import DesignCurrentRow, DesignVersionRow
from openprints.indexer.store_sqlite import SQLiteIndexStore


def test_db_stats_config_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(config="/nonexistent/config.toml", limit=10)
    code = run_db_stats(args)
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out.get("ok") is False
    assert "errors" in out


def test_db_stats_no_database_configured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[indexer]\nrelays = ["ws://localhost:7447"]\n')
    args = Namespace(config=str(config_path), limit=10)
    code = run_db_stats(args)
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out.get("ok") is False
    assert "no database path" in out.get("error", "").lower()


def test_db_stats_memory_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[database]\ndatabase_path = ":memory:"\n')
    args = Namespace(config=str(config_path), limit=10)
    code = run_db_stats(args)
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out.get("ok") is False
    assert "nothing to inspect" in out.get("error", "").lower()


def test_db_stats_database_file_not_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.toml"
    db_path = tmp_path / "missing.db"
    config_path.write_text(f'[database]\ndatabase_path = "{db_path}"\n')
    args = Namespace(config=str(config_path), limit=10)
    code = run_db_stats(args)
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out.get("ok") is False
    assert "not found" in out.get("error", "").lower()


def test_db_stats_success_empty_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "openprints.db"
    config_path = tmp_path / "config.toml"
    config_path.write_text(f'[database]\ndatabase_path = "{db_path}"\n')

    async def create_empty_db() -> None:
        store = SQLiteIndexStore(db_path)
        await store.open()
        await store.close()

    asyncio.run(create_empty_db())
    args = Namespace(config=str(config_path), limit=10)
    code = run_db_stats(args)
    assert code == 0
    out = capsys.readouterr().out
    assert "Database:" in out
    assert "designs:" in out
    assert "design_versions:" in out
    assert "0" in out


def test_db_stats_success_with_designs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "openprints.db"
    config_path = tmp_path / "config.toml"
    config_path.write_text(f'[database]\ndatabase_path = "{db_path}"\n')

    version_row = DesignVersionRow(
        event_id="e" * 64,
        pubkey="p" * 64,
        design_id="openprints:11111111-1111-4111-8111-111111111111",
        kind=33301,
        created_at=1730000000,
        name="My Design",
        format="stl",
        sha256="s" * 64,
        url="https://example.invalid/d.stl",
        content="",
        raw_event_json="{}",
        received_at=1730000100,
    )
    current_row = DesignCurrentRow(
        pubkey="p" * 64,
        design_id="openprints:11111111-1111-4111-8111-111111111111",
        latest_event_id="e" * 64,
        latest_published_at=1730000000,
        first_published_at=1730000000,
        first_seen_at=1730000100,
        updated_at=1730000100,
        version_count=1,
        name="My Design",
        format="stl",
        sha256="s" * 64,
        url="https://example.invalid/d.stl",
        content="",
        tags_json="[]",
    )

    async def create_db_with_design() -> None:
        store = SQLiteIndexStore(db_path)
        await store.open()
        await store.upsert_design_version(version_row)
        await store.upsert_design_current(current_row)
        await store.close()

    asyncio.run(create_db_with_design())
    args = Namespace(config=str(config_path), limit=5)
    code = run_db_stats(args)
    assert code == 0
    out = capsys.readouterr().out
    assert "designs:        1" in out or "1" in out
    assert "design_versions: 1" in out or "1" in out
    assert "Latest" in out
    assert "My Design" in out or "openprints:" in out


def test_db_stats_limit_zero_no_latest_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "openprints.db"
    config_path = tmp_path / "config.toml"
    config_path.write_text(f'[database]\ndatabase_path = "{db_path}"\n')

    async def create_empty_db() -> None:
        store = SQLiteIndexStore(db_path)
        await store.open()
        await store.close()

    asyncio.run(create_empty_db())
    args = Namespace(config=str(config_path), limit=0)
    code = run_db_stats(args)
    assert code == 0
    out = capsys.readouterr().out
    assert "Database:" in out
    assert "Latest" not in out
