from __future__ import annotations

from openprints_cli.error_codes import (
    INVALID_JSON,
    INVALID_TYPE,
    INVALID_VALUE,
    MISSING_REQUIRED_FIELD,
    MISSING_REQUIRED_TAG,
    ErrorCode,
)


def make_error(code: ErrorCode, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def invalid_json(path: str, message: str) -> dict[str, str]:
    return make_error(INVALID_JSON, path, message)


def missing_required_field(path: str) -> dict[str, str]:
    return make_error(MISSING_REQUIRED_FIELD, path, f"{path} is required")


def invalid_type(path: str, expected: str) -> dict[str, str]:
    return make_error(INVALID_TYPE, path, f"{path} must be {expected}")


def invalid_value(path: str, message: str) -> dict[str, str]:
    return make_error(INVALID_VALUE, path, message)


def missing_required_tag(tag_name: str) -> dict[str, str]:
    return make_error(MISSING_REQUIRED_TAG, "event.tags", f"required tag '{tag_name}' is missing")
