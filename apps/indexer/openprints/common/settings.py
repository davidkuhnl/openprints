"""Runtime settings: resolved from config + env + optional CLI overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from openprints.common.config import AppConfig, load_app_config
from openprints.common.errors import invalid_value

ENV_DATABASE_PATH = "OPENPRINTS_INDEX_DATABASE_PATH"
ENV_RELAY_URLS = "OPENPRINTS_RELAY_URLS"
ENV_API_PORT = "OPENPRINTS_API_PORT"
ENV_LOG_LEVEL = "OPENPRINTS_LOG_LEVEL"
ENV_DESIGN_KIND = "OPENPRINTS_DESIGN_KIND"
ENV_DESIGN_QUEUE_MAXSIZE = "OPENPRINTS_DESIGN_QUEUE_MAXSIZE"
ENV_DESIGN_TIMEOUT = "OPENPRINTS_DESIGN_TIMEOUT"
ENV_DESIGN_MAX_RETRIES = "OPENPRINTS_DESIGN_MAX_RETRIES"
ENV_DESIGN_DURATION = "OPENPRINTS_DESIGN_DURATION"

DEFAULT_RELAY_URLS = ["ws://localhost:7447"]


def _normalize_database_path(raw: str | None) -> str | None:
    if not raw or not (v := raw.strip()) or v.lower() in ("log", "none"):
        return None
    return v


@dataclass(frozen=True)
class RuntimeSettings:
    """Fully resolved settings. CLI overrides > env > config > default."""

    database_path: str | None
    relay_urls: tuple[str, ...]
    api_port: int
    api_host: str
    log_level: str
    design_kind: int
    design_queue_maxsize: int
    design_timeout: float
    design_max_retries: int
    design_duration: float
    identity_batch_size: int
    identity_stale_after_s: int
    identity_poll_interval_s: float
    identity_fetch_timeout_s: float


@dataclass
class CliOverrides:
    """Optional CLI overrides; None means use env/config/default."""

    config_path: str | None = None
    port: int | None = None
    host: str | None = None
    log_level: str | None = None
    relay: list[str] | None = None
    design_kind: int | None = None
    design_queue_maxsize: int | None = None
    design_timeout: float | None = None
    design_max_retries: int | None = None
    design_duration: float | None = None


def build_runtime_settings(
    config_path: str | None = None,
    env: Mapping[str, str] | None = None,
    *,
    cli: CliOverrides | None = None,
) -> tuple[RuntimeSettings | None, list[dict[str, str]], str | None]:
    """
    Load config (if any), then resolve every setting: cli > env > config > default.
    Returns (settings, errors, config_path_used).
    """
    env = env if env is not None else os.environ
    cli = cli or CliOverrides()
    effective_config_path = config_path or cli.config_path

    config, errors, path_used = load_app_config(effective_config_path)
    if errors and config is None:
        return None, errors, None
    if config is None:
        config = AppConfig()

    database_path = _resolve_database_path(env, config)
    relay_urls, relay_errors = _resolve_relay_urls(cli, env, config)
    if relay_errors:
        return None, relay_errors, None

    api_port = _resolve_api_port(cli, env, config)
    api_host = _resolve_api_host(cli)
    log_level = _resolve_log_level(cli, env, config)

    design_kind, kind_err = _resolve_int(
        cli.design_kind, ENV_DESIGN_KIND, config.indexer.design_kind, 33301, env, "design_kind"
    )
    if kind_err:
        return None, [kind_err], None

    design_queue_maxsize, q_err = _resolve_int(
        cli.design_queue_maxsize,
        ENV_DESIGN_QUEUE_MAXSIZE,
        config.indexer.design_queue_maxsize,
        1000,
        env,
        "design_queue_maxsize",
    )
    if q_err:
        return None, [q_err], None

    design_timeout, t_err = _resolve_float(
        cli.design_timeout,
        ENV_DESIGN_TIMEOUT,
        config.indexer.design_timeout,
        8.0,
        env,
        "design_timeout",
    )
    if t_err:
        return None, [t_err], None

    design_max_retries, r_err = _resolve_int(
        cli.design_max_retries,
        ENV_DESIGN_MAX_RETRIES,
        config.indexer.design_max_retries,
        12,
        env,
        "design_max_retries",
    )
    if r_err:
        return None, [r_err], None

    design_duration, d_err = _resolve_float(
        cli.design_duration,
        ENV_DESIGN_DURATION,
        config.indexer.design_duration,
        0.0,
        env,
        "design_duration",
    )
    if d_err:
        return None, [d_err], None

    identity_batch_size = config.indexer.identity_batch_size
    identity_stale_after_s = config.indexer.identity_stale_after_s
    identity_poll_interval_s = float(config.indexer.identity_poll_interval_s)
    identity_fetch_timeout_s = float(config.indexer.identity_fetch_timeout_s)

    settings = RuntimeSettings(
        database_path=database_path,
        relay_urls=tuple(relay_urls),
        api_port=api_port,
        api_host=api_host,
        log_level=log_level,
        design_kind=design_kind,
        design_queue_maxsize=design_queue_maxsize,
        design_timeout=design_timeout,
        design_max_retries=design_max_retries,
        design_duration=design_duration,
        identity_batch_size=identity_batch_size,
        identity_stale_after_s=identity_stale_after_s,
        identity_poll_interval_s=identity_poll_interval_s,
        identity_fetch_timeout_s=identity_fetch_timeout_s,
    )
    return settings, [], path_used


def _resolve_database_path(env: Mapping[str, str], config: AppConfig) -> str | None:
    raw = env.get(ENV_DATABASE_PATH, "").strip()
    if raw:
        return _normalize_database_path(raw) or None
    v = config.database.database_path
    return _normalize_database_path(v) if v else None


def _resolve_relay_urls(
    cli: CliOverrides, env: Mapping[str, str], config: AppConfig
) -> tuple[list[str], list[dict[str, str]]]:
    if cli.relay:
        candidates = [x.strip() for x in cli.relay if x and x.strip()]
        if candidates:
            result = list(dict.fromkeys(candidates))
            for r in result:
                if not (r.startswith("ws://") or r.startswith("wss://")):
                    return [], [invalid_value("relay", "relay URL must start with ws:// or wss://")]
            return result, []

    raw = env.get(ENV_RELAY_URLS, "").strip()
    if raw:
        result = [x.strip() for x in raw.split(",") if x.strip()]
        for r in result:
            if not (r.startswith("ws://") or r.startswith("wss://")):
                return [], [invalid_value("relay", "relay URL must start with ws:// or wss://")]
        return list(dict.fromkeys(result)), []

    result = [x for x in (config.indexer.relays or []) if x and x.strip()]
    if not result:
        result = list(DEFAULT_RELAY_URLS)
    for r in result:
        if not (r.startswith("ws://") or r.startswith("wss://")):
            return [], [invalid_value("relay", "relay URL must start with ws:// or wss://")]
    return result, []


def _resolve_api_port(cli: CliOverrides, env: Mapping[str, str], config: AppConfig) -> int:
    if cli.port is not None:
        return cli.port
    raw = env.get(ENV_API_PORT, "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return config.api.api_port


def _resolve_api_host(cli: CliOverrides) -> str:
    if cli.host is not None and cli.host.strip():
        return cli.host.strip()
    return "0.0.0.0"


def _resolve_log_level(cli: CliOverrides, env: Mapping[str, str], config: AppConfig) -> str:
    if cli.log_level is not None and cli.log_level.strip():
        return cli.log_level.strip().upper()
    raw = env.get(ENV_LOG_LEVEL, "").strip()
    if raw:
        return raw.upper()
    return (config.indexer.log_level or "WARNING").upper()


def _resolve_int(
    cli_value: int | None,
    env_name: str,
    config_value: int,
    default: int,
    env: Mapping[str, str],
    path: str,
) -> tuple[int, dict[str, str] | None]:
    if cli_value is not None:
        return cli_value, None
    raw = env.get(env_name, "").strip()
    if raw:
        try:
            return int(raw), None
        except ValueError:
            return default, invalid_value(
                path, f"{path} env override must be an integer ({env_name})"
            )
    return config_value if config_value is not None else default, None


def _resolve_float(
    cli_value: float | None,
    env_name: str,
    config_value: float,
    default: float,
    env: Mapping[str, str],
    path: str,
) -> tuple[float, dict[str, str] | None]:
    if cli_value is not None:
        return cli_value, None
    raw = env.get(env_name, "").strip()
    if raw:
        try:
            return float(raw), None
        except ValueError:
            return default, invalid_value(
                path, f"{path} env override must be a number ({env_name})"
            )
    return float(config_value) if config_value is not None else default, None
