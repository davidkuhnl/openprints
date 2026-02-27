"""Tests for openprints.common.config."""

from __future__ import annotations

from openprints.common.config import (
    DEFAULT_CONFIG_FILENAME,
    ENV_CONFIG_PATH,
    load_app_config,
)


def test_load_indexer_config_none_when_no_file(monkeypatch, tmp_path) -> None:
    import openprints.common.config as config_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
    # Point package dir at tmp_path too so neither cwd nor package has a config file
    monkeypatch.setattr(config_mod, "_PACKAGE_DIR", tmp_path)
    config, errors, path = load_app_config(None)
    assert config == {}
    assert errors == []
    assert path is None


def test_load_indexer_config_loads_index_section(tmp_path) -> None:
    config_file = tmp_path / "custom.toml"
    config_file.write_text(
        '[index]\nrelays = ["ws://localhost:7447"]\nkind = 33301\n',
        encoding="utf-8",
    )
    config, errors, path = load_app_config(str(config_file))
    assert errors == []
    assert config.get("relays") == ["ws://localhost:7447"]
    assert config.get("kind") == 33301
    assert path == str(config_file)


def test_load_indexer_config_relative_path(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / DEFAULT_CONFIG_FILENAME
    config_file.write_text("[index]\nkind = 999\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config, errors, path = load_app_config(DEFAULT_CONFIG_FILENAME)
    assert errors == []
    assert config.get("kind") == 999
    assert path is not None


def test_load_indexer_config_env_override(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "env_config.toml"
    config_file.write_text("[index]\nkind = 111\n", encoding="utf-8")
    monkeypatch.setenv(ENV_CONFIG_PATH, str(config_file))
    config, errors, _ = load_app_config(None)
    assert errors == []
    assert config.get("kind") == 111


def test_load_indexer_config_file_not_found() -> None:
    config, errors, path = load_app_config("/nonexistent/path.toml")
    assert config == {}
    assert len(errors) == 1
    assert "not found" in errors[0].get("message", "")
    assert path is None


def test_load_indexer_config_invalid_toml(tmp_path) -> None:
    config_file = tmp_path / "bad.toml"
    config_file.write_text("not valid toml [", encoding="utf-8")
    config, errors, path = load_app_config(str(config_file))
    assert config == {}
    assert len(errors) == 1
    assert "valid TOML" in errors[0].get("message", "")
    assert path is None


def test_load_indexer_config_os_error_when_path_is_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    # Passing a directory as config path: open(dir, "rb") raises OSError on read
    config, errors, path = load_app_config(str(tmp_path))
    assert config == {}
    assert len(errors) == 1
    assert "unable to read" in errors[0].get("message", "").lower() or "config" in (
        errors[0].get("message", "") or ""
    )
    assert path is None


def test_load_indexer_config_index_section_must_be_dict(tmp_path) -> None:
    config_file = tmp_path / "bad.toml"
    config_file.write_text('index = "not a table"\n', encoding="utf-8")
    config, errors, path = load_app_config(str(config_file))
    assert config == {}
    assert len(errors) == 1
    assert "config.index" in (errors[0].get("path") or errors[0].get("message", ""))
    assert path is None


def test_load_indexer_config_top_level_without_index_section(tmp_path) -> None:
    config_file = tmp_path / "flat.toml"
    config_file.write_text('relays = ["ws://r:7447"]\nkind = 33301\n', encoding="utf-8")
    config, errors, path = load_app_config(str(config_file))
    assert errors == []
    assert config.get("relays") == ["ws://r:7447"]
    assert config.get("kind") == 33301
    assert path is not None


def test_load_indexer_config_uses_openprints_toml_default(monkeypatch, tmp_path) -> None:
    (tmp_path / DEFAULT_CONFIG_FILENAME).write_text("[index]\nkind = 200\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config, errors, path = load_app_config(None)
    assert errors == []
    assert config.get("kind") == 200
    assert path == str(tmp_path / DEFAULT_CONFIG_FILENAME)
