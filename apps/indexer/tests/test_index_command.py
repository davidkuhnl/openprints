from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace

import openprints.cli.commands.index as index_cmd


class _FakeDesignIndexer:
    init_args: dict[str, object] = {}

    def __init__(
        self,
        *,
        relays: list[str],
        kind: int,
        timeout_s: float,
        queue_maxsize: int,
        max_retries: int,
        store=None,
    ) -> None:
        _FakeDesignIndexer.init_args = {
            "relays": relays,
            "kind": kind,
            "timeout_s": timeout_s,
            "queue_maxsize": queue_maxsize,
            "max_retries": max_retries,
        }
        self.reducer = SimpleNamespace(stats=SimpleNamespace(processed=0, reduced=0, duplicates=0))

    async def run(self, stop_event) -> None:
        return


class _FakeIndexerApp:
    ran_for_duration: float | None = None
    ran_until_cancelled: bool = False

    def __init__(self, *, design_indexer: _FakeDesignIndexer, identity_indexer: object) -> None:
        self.design_indexer = design_indexer
        self.identity_indexer = identity_indexer

    async def run_for(self, duration_s: float) -> None:
        _FakeIndexerApp.ran_for_duration = duration_s

    async def run_until_cancelled(self) -> None:
        _FakeIndexerApp.ran_until_cancelled = True

    async def stop(self) -> None:
        return


def _args(**overrides: object) -> Namespace:
    base = {
        "config": None,
        "relay": None,
        "design_kind": None,
        "design_queue_maxsize": None,
        "design_timeout": None,
        "design_max_retries": None,
        "design_duration": None,
    }
    base.update(overrides)
    return Namespace(**base)


def _patch_runtime(monkeypatch) -> None:
    monkeypatch.setattr(index_cmd, "DesignIndexer", _FakeDesignIndexer)
    monkeypatch.setattr(index_cmd, "IndexerApp", _FakeIndexerApp)


def test_index_uses_config_file_defaults(tmp_path, monkeypatch) -> None:
    (tmp_path / "openprints.toml").write_text(
        "\n".join(
            [
                "[indexer]",
                'relays = ["ws://relay-from-config:7447"]',
                "design_kind = 33309",
                "design_queue_maxsize = 77",
                "design_timeout = 2.5",
                "design_max_retries = 4",
                "design_duration = 1.25",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENPRINTS_RELAY_URLS", raising=False)
    _patch_runtime(monkeypatch)

    result = index_cmd.run_index(_args())

    assert result == 0
    assert _FakeDesignIndexer.init_args["relays"] == ["ws://relay-from-config:7447"]
    assert _FakeDesignIndexer.init_args["kind"] == 33309
    assert _FakeDesignIndexer.init_args["queue_maxsize"] == 77
    assert _FakeDesignIndexer.init_args["timeout_s"] == 2.5
    assert _FakeDesignIndexer.init_args["max_retries"] == 4
    assert _FakeIndexerApp.ran_for_duration == 1.25


def test_index_cli_overrides_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        "\n".join(
            [
                "[indexer]",
                'relays = ["ws://relay-from-config:7447"]',
                "design_kind = 12345",
                "design_queue_maxsize = 77",
                "design_timeout = 2.5",
                "design_max_retries = 4",
                "design_duration = 0.5",
            ]
        ),
        encoding="utf-8",
    )
    _patch_runtime(monkeypatch)

    result = index_cmd.run_index(
        _args(
            config=str(config_path),
            relay=["ws://relay-from-cli:7447"],
            design_kind=33301,
            design_queue_maxsize=1000,
            design_timeout=8.0,
            design_max_retries=12,
            design_duration=0.0,
        )
    )

    assert result == 0
    assert _FakeDesignIndexer.init_args["relays"] == ["ws://relay-from-cli:7447"]
    assert _FakeDesignIndexer.init_args["kind"] == 33301
    assert _FakeDesignIndexer.init_args["queue_maxsize"] == 1000
    assert _FakeDesignIndexer.init_args["timeout_s"] == 8.0
    assert _FakeDesignIndexer.init_args["max_retries"] == 12
    assert _FakeIndexerApp.ran_until_cancelled is True


def test_index_config_log_level_applies_when_env_missing(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        "\n".join(
            [
                "[indexer]",
                "log_level = 'INFO'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENPRINTS_LOG_LEVEL", raising=False)
    _patch_runtime(monkeypatch)

    result = index_cmd.run_index(_args(config=str(config_path), design_duration=0.01))

    assert result == 0
    assert _FakeIndexerApp.ran_for_duration == 0.01
    assert index_cmd.os.environ.get("OPENPRINTS_LOG_LEVEL") == "INFO"


def test_index_returns_1_when_config_file_not_found(capsys) -> None:
    result = index_cmd.run_index(_args(config="/nonexistent/config.toml"))
    assert result == 1
    out = capsys.readouterr()
    assert "ok" in out.out.lower() or "error" in out.out.lower()


def test_index_returns_1_when_config_relays_invalid_type(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text("[indexer]\nrelays = [123]\n", encoding="utf-8")
    _patch_runtime(monkeypatch)
    result = index_cmd.run_index(_args(config=str(config_path), relay=["ws://r:7447"]))
    assert result == 1


def test_index_returns_1_when_relay_url_invalid(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        '[indexer]\nrelays = ["http://invalid:7447"]\n',
        encoding="utf-8",
    )
    _patch_runtime(monkeypatch)
    result = index_cmd.run_index(_args(config=str(config_path), design_duration=0.01))
    assert result == 1


def test_index_returns_1_when_config_design_kind_invalid_type(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        '[indexer]\nrelays = ["ws://r:7447"]\ndesign_kind = "33301"\n',
        encoding="utf-8",
    )
    _patch_runtime(monkeypatch)
    result = index_cmd.run_index(_args(config=str(config_path)))
    assert result == 1


def test_index_returns_1_when_config_log_level_invalid(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        '[indexer]\nrelays = ["ws://r:7447"]\nlog_level = "TRACE"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENPRINTS_LOG_LEVEL", raising=False)
    _patch_runtime(monkeypatch)
    result = index_cmd.run_index(_args(config=str(config_path), design_duration=0.01))
    assert result == 1


def test_index_returns_1_when_design_max_retries_negative(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        '[indexer]\nrelays = ["ws://r:7447"]\ndesign_max_retries = -1\n',
        encoding="utf-8",
    )
    _patch_runtime(monkeypatch)
    result = index_cmd.run_index(_args(config=str(config_path), design_duration=0.01))
    assert result == 1


def test_index_returns_1_when_design_duration_negative(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        '[indexer]\nrelays = ["ws://r:7447"]\ndesign_duration = -1.0\n',
        encoding="utf-8",
    )
    _patch_runtime(monkeypatch)
    result = index_cmd.run_index(_args(config=str(config_path)))
    assert result == 1


def test_index_prints_stats_on_success(tmp_path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        '[indexer]\nrelays = ["ws://r:7447"]\ndesign_duration = 0.001\n',
        encoding="utf-8",
    )
    _patch_runtime(monkeypatch)
    result = index_cmd.run_index(_args(config=str(config_path)))
    assert result == 0
    out = capsys.readouterr().out
    assert "ok" in out
    assert "stats" in out or "relays" in out
