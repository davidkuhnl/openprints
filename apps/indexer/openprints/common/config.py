from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, StrictFloat, StrictInt, field_validator

from openprints.common.error_codes import INVALID_TYPE, INVALID_VALUE
from openprints.common.errors import make_error

ENV_CONFIG_PATH = "OPENPRINTS_CONFIG"
DEFAULT_CONFIG_FILENAME = "openprints.toml"

_LOG_LEVEL = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

# Directory containing this module; used as fallback search path for default config.
_PACKAGE_DIR = Path(__file__).resolve().parent


def _normalize_database_path(raw: str | None) -> str | None:
    if not raw or not (v := raw.strip()) or v.lower() in ("log", "none"):
        return None
    return v


class DatabaseConfig(BaseModel):
    """Database path shared by indexer and API. Omit or set to 'log' for log-only."""

    database_path: str | None = None

    @field_validator("database_path", mode="before")
    @classmethod
    def coerce_path(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            return _normalize_database_path(v) or None
        return None


class IndexerConfig(BaseModel):
    """Indexer-specific settings: relays, kind, queue, timeouts, log level."""

    relays: list[str] = Field(default_factory=list)
    kind: StrictInt = 33301
    queue_maxsize: StrictInt = 1000
    timeout: StrictFloat = 8.0
    max_retries: StrictInt = 12
    duration: StrictFloat = 0.0
    log_level: _LOG_LEVEL = "WARNING"

    @field_validator("log_level", mode="before")
    @classmethod
    def uppercase_log_level(cls, v: object) -> str:
        if v is None:
            return "WARNING"
        if isinstance(v, str):
            return v.strip().upper()
        raise ValueError("log_level must be a string")

    @field_validator("relays", mode="before")
    @classmethod
    def strip_relays(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("relays must be a list of strings")
        out: list[str] = []
        for x in v:
            if not isinstance(x, str):
                raise ValueError("relays must be a list of strings")
            if x.strip():
                out.append(x.strip())
        return out


class ApiConfig(BaseModel):
    """API server settings."""

    api_port: StrictInt = 8080


class AppConfig(BaseModel):
    """Full application config: database, indexer, and api sections."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    indexer: IndexerConfig = Field(default_factory=IndexerConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)


def _pydantic_errors_to_list(exc: Exception) -> list[dict[str, str]]:
    from pydantic import ValidationError

    if not isinstance(exc, ValidationError):
        return [make_error(INVALID_VALUE, "config", str(exc))]
    out: list[dict[str, str]] = []
    for err in exc.errors():
        locs = [str(loc) for loc in err["loc"] if isinstance(loc, (str, int))]
        path = "config." + ".".join(locs) if locs else "config"
        msg = err.get("msg", "validation error")
        out.append(make_error(INVALID_TYPE, path, msg))
    return out


def load_app_config(
    config_path: str | None,
) -> tuple[AppConfig | None, list[dict[str, str]], str | None]:
    """Load TOML config into typed AppConfig. Returns (config, errors, path)."""
    path_value = (config_path or "").strip() or os.environ.get(ENV_CONFIG_PATH, "").strip()

    if path_value:
        path = Path(path_value)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            return (
                None,
                [make_error(INVALID_VALUE, "config", f"config file not found: {path}")],
                None,
            )
    else:
        path = _resolve_default_config_path()
        if path is None:
            return AppConfig(), [], None

    try:
        with path.open("rb") as f:
            parsed = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        return (
            None,
            [make_error(INVALID_VALUE, "config", f"config file is not valid TOML ({exc})")],
            None,
        )
    except OSError as exc:
        return (
            None,
            [make_error(INVALID_VALUE, "config", f"unable to read config file: {exc}")],
            None,
        )

    if not isinstance(parsed, dict):
        return None, [make_error(INVALID_TYPE, "config", "a TOML table/object")], None

    # Build section dicts; allow [indexer] or legacy [index] for indexer section
    database_raw = parsed.get("database")
    if database_raw is not None and not isinstance(database_raw, dict):
        return None, [make_error(INVALID_TYPE, "config.database", "a TOML table/object")], None

    indexer_raw = parsed.get("indexer") or parsed.get("index")
    if indexer_raw is not None and not isinstance(indexer_raw, dict):
        return None, [make_error(INVALID_TYPE, "config.indexer", "a TOML table/object")], None

    api_raw = parsed.get("api")
    if api_raw is not None and not isinstance(api_raw, dict):
        return None, [make_error(INVALID_TYPE, "config.api", "a TOML table/object")], None

    try:
        config = AppConfig(
            database=DatabaseConfig(**(database_raw or {})),
            indexer=IndexerConfig(**(indexer_raw or {})),
            api=ApiConfig(**(api_raw or {})),
        )
    except Exception as exc:
        return None, _pydantic_errors_to_list(exc), None

    return config, [], str(path)


def _resolve_default_config_path() -> Path | None:
    for base_dir in (Path.cwd(), _PACKAGE_DIR):
        candidate = base_dir / DEFAULT_CONFIG_FILENAME
        if candidate.exists():
            return candidate
    return None
