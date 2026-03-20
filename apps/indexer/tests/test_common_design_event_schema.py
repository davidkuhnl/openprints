from openprints.common.design_event_schema import (
    LEGACY_SCHEMA_VERSION,
    UNKNOWN_SCHEMA_VERSION,
    resolve_design_event_schema_version,
)
from tests.test_helpers import valid_signed_payload


def test_resolve_schema_defaults_to_legacy_when_tag_missing() -> None:
    event = valid_signed_payload()["event"]
    assert resolve_design_event_schema_version(event) == LEGACY_SCHEMA_VERSION


def test_resolve_schema_reads_tag_value_when_present() -> None:
    event = dict(valid_signed_payload()["event"])
    event["tags"] = [
        [entry[0], entry[1]]
        for entry in event["tags"]
        if isinstance(entry, list) and len(entry) >= 2
    ] + [["openprints_schema", "1.1"]]
    assert resolve_design_event_schema_version(event) == "1.1"


def test_resolve_schema_returns_unknown_for_malformed_schema_tag() -> None:
    event = dict(valid_signed_payload()["event"])
    event["tags"] = [
        [entry[0], entry[1]]
        for entry in event["tags"]
        if isinstance(entry, list) and len(entry) >= 2
    ] + [["openprints_schema"]]
    assert resolve_design_event_schema_version(event) == UNKNOWN_SCHEMA_VERSION
