"""Tests for openprints.common.config and openprints.common.settings."""

from __future__ import annotations

from openprints.common.config import (
    DEFAULT_CONFIG_FILENAME,
    ENV_CONFIG_PATH,
    AppConfig,
    load_app_config,
)
from openprints.common.settings import build_runtime_settings


def test_load_app_config_none_when_no_file(monkeypatch, tmp_path) -> None:
    import openprints.common.config as config_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
    monkeypatch.setattr(config_mod, "_PACKAGE_DIR", tmp_path)
    config, errors, path = load_app_config(None)
    assert config is not None
    assert isinstance(config, AppConfig)
    assert config.indexer.kind == 33301
    assert errors == []
    assert path is None


def test_load_app_config_loads_indexer_section(tmp_path) -> None:
    config_file = tmp_path / "custom.toml"
    config_file.write_text(
        '[indexer]\nrelays = ["ws://localhost:7447"]\nkind = 33301\n',
        encoding="utf-8",
    )
    config, errors, path = load_app_config(str(config_file))
    assert errors == []
    assert config is not None
    assert config.indexer.relays == ["ws://localhost:7447"]
    assert config.indexer.kind == 33301
    assert path == str(config_file)


def test_load_app_config_relative_path(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / DEFAULT_CONFIG_FILENAME
    config_file.write_text("[indexer]\nkind = 999\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config, errors, path = load_app_config(DEFAULT_CONFIG_FILENAME)
    assert errors == []
    assert config is not None
    assert config.indexer.kind == 999
    assert path is not None


def test_load_app_config_env_override(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "env_config.toml"
    config_file.write_text("[indexer]\nkind = 111\n", encoding="utf-8")
    monkeypatch.setenv(ENV_CONFIG_PATH, str(config_file))
    config, errors, _ = load_app_config(None)
    assert errors == []
    assert config is not None
    assert config.indexer.kind == 111


def test_load_app_config_file_not_found() -> None:
    config, errors, path = load_app_config("/nonexistent/path.toml")
    assert config is None
    assert len(errors) == 1
    assert "not found" in errors[0].get("message", "")
    assert path is None


def test_load_app_config_invalid_toml(tmp_path) -> None:
    config_file = tmp_path / "bad.toml"
    config_file.write_text("not valid toml [", encoding="utf-8")
    config, errors, path = load_app_config(str(config_file))
    assert config is None
    assert len(errors) == 1
    assert "valid TOML" in errors[0].get("message", "")
    assert path is None


def test_load_app_config_os_error_when_path_is_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    config, errors, path = load_app_config(str(tmp_path))
    assert config is None
    assert len(errors) == 1
    assert "unable to read" in errors[0].get("message", "").lower() or "config" in (
        errors[0].get("message", "") or ""
    )
    assert path is None


def test_load_app_config_indexer_section_must_be_dict(tmp_path) -> None:
    config_file = tmp_path / "bad.toml"
    config_file.write_text('indexer = "not a table"\n', encoding="utf-8")
    config, errors, path = load_app_config(str(config_file))
    assert config is None
    assert len(errors) == 1
    assert "config.indexer" in (errors[0].get("path") or errors[0].get("message", ""))
    assert path is None


def test_load_app_config_database_and_api_sections(tmp_path) -> None:
    config_file = tmp_path / "full.toml"
    config_file.write_text(
        '[database]\ndatabase_path = "openprints.db"\n'
        '[indexer]\nrelays = ["ws://r:7447"]\nkind = 33301\n'
        "[api]\napi_port = 9000\n",
        encoding="utf-8",
    )
    config, errors, path = load_app_config(str(config_file))
    assert errors == []
    assert config is not None
    assert config.database.database_path == "openprints.db"
    assert config.indexer.relays == ["ws://r:7447"]
    assert config.api.api_port == 9000
    assert path is not None


def test_resolve_database_path_from_config(tmp_path) -> None:
    config_file = tmp_path / "db.toml"
    config_file.write_text('[database]\ndatabase_path = "openprints.db"\n', encoding="utf-8")
    settings, errors, _ = build_runtime_settings(config_path=str(config_file))
    assert errors == []
    assert settings is not None
    assert settings.database_path == "openprints.db"

    config_file.write_text("[database]\n", encoding="utf-8")
    settings, errors, _ = build_runtime_settings(config_path=str(config_file))
    assert errors == []
    assert settings is not None
    assert settings.database_path is None


def test_resolve_database_path_log_none(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OPENPRINTS_INDEX_DATABASE_PATH", raising=False)
    config_file = tmp_path / "db.toml"
    config_file.write_text('[database]\ndatabase_path = "log"\n', encoding="utf-8")
    settings, errors, _ = build_runtime_settings(config_path=str(config_file))
    assert errors == []
    assert settings is not None
    assert settings.database_path is None

    config_file.write_text('[database]\ndatabase_path = "none"\n', encoding="utf-8")
    settings, errors, _ = build_runtime_settings(config_path=str(config_file))
    assert errors == []
    assert settings is not None
    assert settings.database_path is None
