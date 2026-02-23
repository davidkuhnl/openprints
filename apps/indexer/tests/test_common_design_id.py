"""Tests for openprints.common.design_id."""

from uuid import UUID

from openprints.common.design_id import is_valid_openprints_design_id, normalize_design_id
from openprints.common.error_codes import INVALID_VALUE


def test_is_valid_accepts_openprints_prefix_uuid_v4() -> None:
    assert is_valid_openprints_design_id("openprints:00000000-0000-4000-8000-000000000000") is True
    assert is_valid_openprints_design_id("openprints:3f17122b-6547-42db-a9ac-d76a61c5e1cc") is True


def test_is_valid_accepts_bare_uuid_v4() -> None:
    assert is_valid_openprints_design_id("00000000-0000-4000-8000-000000000000") is True
    assert is_valid_openprints_design_id("3f17122b-6547-42db-a9ac-d76a61c5e1cc") is True


def test_is_valid_rejects_non_uuid() -> None:
    assert is_valid_openprints_design_id("openprints:stub-design-id") is False
    assert is_valid_openprints_design_id("openprints:abc") is False
    assert is_valid_openprints_design_id("not-a-uuid") is False


def test_is_valid_rejects_empty_or_none_like() -> None:
    assert is_valid_openprints_design_id("") is False


def test_is_valid_rejects_uuid_v1() -> None:
    # UUID v1 has version digit 1 in 13th position
    assert is_valid_openprints_design_id("openprints:550e8400-e29b-11d4-a716-446655440000") is False


def test_normalize_design_id_none_generates() -> None:
    canonical, generated, errors = normalize_design_id(None)
    assert canonical is not None
    assert canonical.startswith("openprints:")
    assert UUID(canonical[len("openprints:") :]).version == 4
    assert generated is True
    assert errors == []


def test_normalize_design_id_prefixed_returns_canonical() -> None:
    canonical, generated, errors = normalize_design_id(
        "openprints:3f17122b-6547-42db-a9ac-d76a61c5e1cc"
    )
    assert canonical == "openprints:3f17122b-6547-42db-a9ac-d76a61c5e1cc"
    assert generated is False
    assert errors == []


def test_normalize_design_id_bare_uuid_adds_prefix() -> None:
    canonical, generated, errors = normalize_design_id("3f17122b-6547-42db-a9ac-d76a61c5e1cc")
    assert canonical == "openprints:3f17122b-6547-42db-a9ac-d76a61c5e1cc"
    assert generated is False
    assert errors == []


def test_normalize_design_id_invalid_returns_errors() -> None:
    canonical, generated, errors = normalize_design_id("openprints:abc")
    assert canonical is None
    assert generated is False
    assert len(errors) == 1
    assert errors[0]["code"] == INVALID_VALUE
    assert "valid UUID" in errors[0]["message"]


def test_normalize_design_id_non_v4_returns_errors() -> None:
    canonical, generated, errors = normalize_design_id("550e8400-e29b-11d4-a716-446655440000")
    assert canonical is None
    assert generated is False
    assert len(errors) == 1
    assert errors[0]["code"] == INVALID_VALUE
    assert "version 4" in errors[0]["message"]
