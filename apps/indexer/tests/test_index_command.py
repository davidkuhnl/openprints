from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace

import openprints.cli.commands.index as index_cmd


class _FakeCoordinator:
    init_args: dict[str, object] = {}
    ran_for_duration: float | None = None
    ran_until_cancelled: bool = False

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
        _FakeCoordinator.init_args = {
            "relays": relays,
            "kind": kind,
            "timeout_s": timeout_s,
            "queue_maxsize": queue_maxsize,
            "max_retries": max_retries,
        }
        self.reducer = SimpleNamespace(stats=SimpleNamespace(processed=0, reduced=0, duplicates=0))

    async def run_for(self, duration_s: float) -> None:
        _FakeCoordinator.ran_for_duration = duration_s

    async def run_until_cancelled(self) -> None:
        _FakeCoordinator.ran_until_cancelled = True


def _args(**overrides: object) -> Namespace:
    base = {
        "config": None,
        "relay": None,
        "kind": None,
        "queue_maxsize": None,
        "timeout": None,
        "max_retries": None,
        "duration": None,
    }
    base.update(overrides)
    return Namespace(**base)


def test_index_uses_config_file_defaults(tmp_path, monkeypatch) -> None:
    (tmp_path / "openprints.indexer.toml").write_text(
        "\n".join(
            [
                "[index]",
                'relays = ["ws://relay-from-config:7447"]',
                "kind = 33309",
                "queue_maxsize = 77",
                "timeout = 2.5",
                "max_retries = 4",
                "duration = 1.25",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENPRINTS_RELAY_URL", raising=False)
    monkeypatch.delenv("OPENPRINTS_RELAY_URLS", raising=False)
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)

    result = index_cmd.run_index(_args())

    assert result == 0
    assert _FakeCoordinator.init_args["relays"] == ["ws://relay-from-config:7447"]
    assert _FakeCoordinator.init_args["kind"] == 33309
    assert _FakeCoordinator.init_args["queue_maxsize"] == 77
    assert _FakeCoordinator.init_args["timeout_s"] == 2.5
    assert _FakeCoordinator.init_args["max_retries"] == 4
    assert _FakeCoordinator.ran_for_duration == 1.25


def test_index_cli_overrides_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        "\n".join(
            [
                "[index]",
                'relays = ["ws://relay-from-config:7447"]',
                "kind = 12345",
                "queue_maxsize = 77",
                "timeout = 2.5",
                "max_retries = 4",
                "duration = 0.5",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)

    result = index_cmd.run_index(
        _args(
            config=str(config_path),
            relay=["ws://relay-from-cli:7447"],
            kind=33301,
            queue_maxsize=1000,
            timeout=8.0,
            max_retries=12,
            duration=0.0,
        )
    )

    assert result == 0
    assert _FakeCoordinator.init_args["relays"] == ["ws://relay-from-cli:7447"]
    assert _FakeCoordinator.init_args["kind"] == 33301
    assert _FakeCoordinator.init_args["queue_maxsize"] == 1000
    assert _FakeCoordinator.init_args["timeout_s"] == 8.0
    assert _FakeCoordinator.init_args["max_retries"] == 12
    assert _FakeCoordinator.ran_until_cancelled is True


def test_index_config_log_level_applies_when_env_missing(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        "\n".join(
            [
                "[index]",
                "log_level = 'INFO'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENPRINTS_LOG_LEVEL", raising=False)
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)

    result = index_cmd.run_index(_args(config=str(config_path), duration=0.01))

    assert result == 0
    assert _FakeCoordinator.ran_for_duration == 0.01
    assert index_cmd.os.environ.get("OPENPRINTS_LOG_LEVEL") == "INFO"


def test_index_returns_1_when_config_file_not_found(capsys) -> None:
    result = index_cmd.run_index(_args(config="/nonexistent/config.toml"))
    assert result == 1
    out = capsys.readouterr()
    assert "ok" in out.out.lower() or "error" in out.out.lower()


def test_index_returns_1_when_config_relays_invalid_type(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text("[index]\nrelays = [123]\n", encoding="utf-8")
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path), relay=["ws://r:7447"]))
    assert result == 1


def test_index_returns_1_when_relay_url_invalid(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["http://invalid:7447"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path), duration=0.01))
    assert result == 1


def test_index_returns_1_when_config_kind_invalid_type(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["ws://r:7447"]\nkind = "33301"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path)))
    assert result == 1


def test_index_returns_1_when_config_log_level_invalid(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["ws://r:7447"]\nlog_level = "TRACE"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENPRINTS_LOG_LEVEL", raising=False)
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path), duration=0.01))
    assert result == 1


def test_index_returns_1_when_max_retries_negative(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["ws://r:7447"]\nmax_retries = -1\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path), duration=0.01))
    assert result == 1


def test_index_returns_1_when_duration_negative(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["ws://r:7447"]\nduration = -1.0\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path)))
    assert result == 1


def test_index_prints_stats_on_success(tmp_path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["ws://r:7447"]\nduration = 0.001\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path)))
    assert result == 0
    out = capsys.readouterr().out
    assert "ok" in out
    assert "stats" in out or "relays" in out


def test_index_health_port_from_config_calls_start_health_server(
    tmp_path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["ws://r:7447"]\nduration = 0.01\nhealth_port = 8080\n',
        encoding="utf-8",
    )
    start_calls: list[dict[str, object]] = []
    fake_server = type(
        "FakeServer",
        (),
        {"shutdown": lambda self: None, "server_address": ("", 8080)},
    )()

    def capture_start(port: int, *, database_path=None, relay_urls=None):  # noqa: ANN001
        start_calls.append(
            {
                "port": port,
                "database_path": database_path,
                "relay_urls": relay_urls,
            }
        )
        return fake_server

    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    monkeypatch.setattr(index_cmd, "start_health_server", capture_start)
    result = index_cmd.run_index(_args(config=str(config_path)))
    assert result == 0
    assert len(start_calls) == 1
    assert start_calls[0]["port"] == 8080
    assert start_calls[0]["relay_urls"] == ["ws://r:7447"]


def test_index_returns_1_when_health_port_negative(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["ws://r:7447"]\nhealth_port = -1\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path), duration=0.01))
    assert result == 1


def test_index_returns_1_when_health_port_env_invalid(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "openprints.indexer.toml"
    config_path.write_text(
        '[index]\nrelays = ["ws://r:7447"]\nduration = 0.01\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENPRINTS_HEALTH_PORT", "notanint")
    monkeypatch.setattr(index_cmd, "IndexerCoordinator", _FakeCoordinator)
    result = index_cmd.run_index(_args(config=str(config_path)))
    assert result == 1
