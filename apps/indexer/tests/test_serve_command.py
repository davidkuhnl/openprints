from __future__ import annotations

import sys
from argparse import Namespace
from types import SimpleNamespace

import openprints.cli.commands.serve as serve_cmd


def _args(**overrides: object) -> Namespace:
    base = {"config": None, "port": None, "host": None, "log_level": None}
    base.update(overrides)
    return Namespace(**base)


def test_serve_uses_api_logging_not_indexer_logging(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENPRINTS_LOG_LEVEL", raising=False)
    monkeypatch.delenv("OPENPRINTS_API_LOG_LEVEL", raising=False)
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        "\n".join(
            [
                "[indexer]",
                "log_level = 'ERROR'",
                f"log_folder = '{tmp_path.as_posix()}/indexer'",
                "log_base_name = 'indexer'",
                "",
                "[api]",
                "api_port = 9001",
                "log_level = 'INFO'",
                f"log_folder = '{tmp_path.as_posix()}/api'",
                "log_base_name = 'api'",
            ]
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def _fake_run(*args, **kwargs):
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr(serve_cmd, "configure_logging", lambda: None)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=_fake_run))

    result = serve_cmd.run_serve(_args(config=str(config_path)))

    assert result == 0
    assert serve_cmd.os.environ.get("OPENPRINTS_LOG_LEVEL") == "INFO"
    assert serve_cmd.os.environ.get("OPENPRINTS_LOG_FOLDER") == f"{tmp_path.as_posix()}/api"
    assert serve_cmd.os.environ.get("OPENPRINTS_LOG_BASE_NAME") == "api"
    kwargs = captured["kwargs"]
    assert kwargs["port"] == 9001
    assert kwargs["log_config"]["loggers"]["uvicorn"]["level"] == "INFO"


def test_serve_cli_log_level_overrides_api_log_level(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENPRINTS_LOG_LEVEL", raising=False)
    monkeypatch.delenv("OPENPRINTS_API_LOG_LEVEL", raising=False)
    config_path = tmp_path / "openprints.toml"
    config_path.write_text(
        "\n".join(
            [
                "[api]",
                "log_level = 'WARNING'",
            ]
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def _fake_run(*args, **kwargs):
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr(serve_cmd, "configure_logging", lambda: None)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=_fake_run))

    result = serve_cmd.run_serve(_args(config=str(config_path), log_level="debug"))

    assert result == 0
    assert serve_cmd.os.environ.get("OPENPRINTS_LOG_LEVEL") == "DEBUG"
    kwargs = captured["kwargs"]
    assert kwargs["log_config"]["loggers"]["uvicorn"]["level"] == "DEBUG"
