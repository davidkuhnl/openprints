import json
from argparse import Namespace
from pathlib import Path
from uuid import UUID

import openprints.cli.commands.build as build_cmd
from openprints.cli.commands.build import run_build_design, run_build_identity
from openprints.common.error_codes import INVALID_VALUE, MISSING_REQUIRED_FIELD

FIXTURE_FILE = Path(__file__).parent / "fixtures" / "stub_design.stl"
FIXTURE_SHA256 = "fc1b7cc223d252f88ddf568a83fe5a446a21d9358cb69cb3d6374c181cc4f3cd"


def _build_design_args(**overrides: object) -> Namespace:
    base = {
        "name": "Stub Design",
        "design_id": None,
        "format": "stl",
        "url": "https://example.invalid/stub.stl",
        "content": "Stub payload from tests.",
        "file": str(FIXTURE_FILE),
        "sha256": None,
        "output": "-",
    }
    base.update(overrides)
    return Namespace(**base)


def _build_identity_args(**overrides: object) -> Namespace:
    profile_file = Path(__file__).parent / "fixtures" / "stub_profile.json"
    base = {
        "profile_file": str(profile_file),
        "output": "-",
    }
    base.update(overrides)
    return Namespace(**base)


def _tag_value(payload: dict, key: str) -> str:
    for tag in payload["event"]["tags"]:
        if len(tag) >= 2 and tag[0] == key:
            return tag[1]
    raise AssertionError(f"missing tag: {key}")


def test_build_to_stdout_emits_json_payload(capsys) -> None:
    result = run_build_design(_build_design_args(output="-"))
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert payload["artifact_version"] == 1
    assert payload["meta"]["state"] == "draft"
    assert payload["meta"]["event_type"] == "design"
    assert payload["event"]["kind"] == 33301
    assert _tag_value(payload, "openprints_schema") == "1.1"
    assert _tag_value(payload, "sha256") == FIXTURE_SHA256
    assert "build: wrote payload JSON to stdout." in captured.err


def test_build_to_file_writes_json_payload(tmp_path: Path, capsys) -> None:
    output_file = tmp_path / "payload.json"
    result = run_build_design(_build_design_args(output=str(output_file)))
    captured = capsys.readouterr()

    assert result == 0
    assert output_file.exists()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["artifact_version"] == 1
    assert payload["meta"]["state"] == "draft"
    assert payload["meta"]["event_type"] == "design"
    assert payload["event"]["kind"] == 33301
    assert _tag_value(payload, "openprints_schema") == "1.1"
    assert _tag_value(payload, "sha256") == FIXTURE_SHA256
    assert f"build: wrote payload JSON to {output_file}." in captured.out


def test_build_with_sha256_argument(capsys) -> None:
    result = run_build_design(
        _build_design_args(
            file=None,
            sha256=FIXTURE_SHA256,
            output="-",
        )
    )
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert _tag_value(payload, "sha256") == FIXTURE_SHA256


def test_build_autogenerates_design_id_when_missing(capsys) -> None:
    result = run_build_design(_build_design_args(design_id=None, output="-"))
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    design_id = _tag_value(payload, "d")
    assert design_id.startswith("openprints:")
    assert UUID(design_id.replace("openprints:", "")).version == 4
    assert "build: generated design id for d tag." in captured.err


def test_build_accepts_prefixed_design_id_and_normalizes(capsys) -> None:
    result = run_build_design(
        _build_design_args(
            design_id="openprints:3f17122b-6547-42db-a9ac-d76a61c5e1cc",
            output="-",
        )
    )
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert _tag_value(payload, "d") == "openprints:3f17122b-6547-42db-a9ac-d76a61c5e1cc"
    assert "build: generated design id for d tag." not in captured.err


def test_build_accepts_bare_uuid_design_id(capsys) -> None:
    result = run_build_design(
        _build_design_args(
            design_id="3f17122b-6547-42db-a9ac-d76a61c5e1cc",
            output="-",
        )
    )
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert _tag_value(payload, "d") == "openprints:3f17122b-6547-42db-a9ac-d76a61c5e1cc"


def test_build_rejects_invalid_sha256(capsys) -> None:
    result = run_build_design(_build_design_args(file=None, sha256="abc", output="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.err)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE


def test_build_rejects_invalid_design_id(capsys) -> None:
    result = run_build_design(_build_design_args(design_id="not-a-uuid", output="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.err)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE


def test_build_handles_internal_validation_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        build_cmd,
        "validate_payload",
        lambda _payload: [
            {
                "code": MISSING_REQUIRED_FIELD,
                "path": "event.kind",
                "message": "event.kind is required",
            }
        ],
    )

    result = run_build_design(_build_design_args(output="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.err)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == MISSING_REQUIRED_FIELD


def test_build_identity_to_stdout_emits_json_payload(capsys) -> None:
    result = run_build_identity(_build_identity_args(output="-"))
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert payload["artifact_version"] == 1
    assert payload["meta"]["state"] == "draft"
    assert payload["meta"]["event_type"] == "identity"
    assert payload["event"]["kind"] == 0
    assert payload["event"]["tags"] == []
    assert isinstance(json.loads(payload["event"]["content"]), dict)


def test_build_identity_rejects_invalid_json_file(tmp_path: Path, capsys) -> None:
    profile_file = tmp_path / "bad_profile.json"
    profile_file.write_text("{bad-json", encoding="utf-8")

    result = run_build_identity(_build_identity_args(profile_file=str(profile_file), output="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.err)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE
