from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from openprints.common.errors import invalid_type, invalid_value

DEFAULT_CONFIG_FILENAME = "openprints.indexer.toml"
ENV_CONFIG_PATH = "OPENPRINTS_INDEXER_CONFIG"

# Directory containing this module; used as fallback search path for default config.
_PACKAGE_DIR = Path(__file__).resolve().parent


def load_indexer_config(
    config_path: str | None,
) -> tuple[dict[str, Any], list[dict[str, str]], str | None]:
    path_value = (config_path or "").strip() or os.environ.get(ENV_CONFIG_PATH, "").strip()
    if path_value:
        path = Path(path_value)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            return {}, [invalid_value("config", f"config file not found: {path}")], None
    else:
        # Try cwd first, then directory containing this module.
        path = Path.cwd() / DEFAULT_CONFIG_FILENAME
        if not path.exists():
            path = _PACKAGE_DIR / DEFAULT_CONFIG_FILENAME
        if not path.exists():
            return {}, [], None

    try:
        with path.open("rb") as file_obj:
            parsed = tomllib.load(file_obj)
    except tomllib.TOMLDecodeError as exc:
        return {}, [invalid_value("config", f"config file is not valid TOML ({exc})")], None
    except OSError as exc:
        return {}, [invalid_value("config", f"unable to read config file: {exc}")], None

    if not isinstance(parsed, dict):
        return {}, [invalid_type("config", "a TOML table/object")], None

    if "index" in parsed:
        index_config = parsed["index"]
        if not isinstance(index_config, dict):
            return {}, [invalid_type("config.index", "a TOML table/object")], None
        return dict(index_config), [], str(path)

    return dict(parsed), [], str(path)
