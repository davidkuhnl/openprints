import json
from argparse import Namespace
from pathlib import Path

import openprints_cli.commands.build as build_cmd
from openprints_cli.commands.build import run_build
from openprints_cli.error_codes import MISSING_REQUIRED_FIELD


def test_build_to_stdout_emits_json_payload(capsys) -> None:
    result = run_build(Namespace(output="-"))
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert payload["artifact_version"] == 1
    assert payload["meta"]["state"] == "draft"
    assert payload["event"]["kind"] == 33301
    assert "build: wrote payload JSON to stdout." in captured.err


def test_build_to_file_writes_json_payload(tmp_path: Path, capsys) -> None:
    output_file = tmp_path / "payload.json"
    result = run_build(Namespace(output=str(output_file)))
    captured = capsys.readouterr()

    assert result == 0
    assert output_file.exists()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["artifact_version"] == 1
    assert payload["meta"]["state"] == "draft"
    assert payload["event"]["kind"] == 33301
    assert f"build: wrote payload JSON to {output_file}." in captured.out


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

    result = run_build(Namespace(output="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.err)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == MISSING_REQUIRED_FIELD
