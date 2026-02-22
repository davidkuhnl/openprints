import json
import sys
from argparse import Namespace
from io import StringIO
from pathlib import Path

import openprints_cli.commands.build as build_cmd
from openprints_cli.commands.build import run_build
from openprints_cli.commands.publish import run_publish
from openprints_cli.commands.subscribe import run_subscribe
from openprints_cli.error_codes import INVALID_JSON, MISSING_REQUIRED_FIELD
from openprints_cli.main import main


def _valid_draft_payload() -> dict:
    return {
        "artifact_version": 1,
        "meta": {"state": "draft", "source": "openprints-cli"},
        "event": {
            "kind": 33301,
            "created_at": 1730000000,
            "tags": [
                ["d", "openprints:stub-design-id"],
                ["name", "Stub Design"],
                ["format", "stl"],
                ["sha256", "0000000000000000000000000000000000000000000000000000000000000000"],
                ["url", "https://example.invalid/stub.stl"],
            ],
            "content": "Stub payload from tests.",
        },
    }


def test_cli_help_shows_subcommands(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["openprints-cli"])
    result = main()
    captured = capsys.readouterr()

    assert result == 0
    assert "openprints-cli" in captured.out
    assert "build" in captured.out
    assert "publish" in captured.out
    assert "subscribe" in captured.out


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


def test_publish_reads_payload_from_file(tmp_path: Path, capsys) -> None:
    input_file = tmp_path / "payload.json"
    input_file.write_text(
        json.dumps(_valid_draft_payload()),
        encoding="utf-8",
    )

    result = run_publish(Namespace(input=str(input_file)))
    captured = capsys.readouterr()

    assert result == 0
    assert "publish: would sign and publish this payload" in captured.out
    assert '"artifact_version": 1' in captured.out


def test_publish_reads_payload_from_stdin(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "stdin",
        StringIO(json.dumps(_valid_draft_payload())),
    )

    result = run_publish(Namespace(input="-"))
    captured = capsys.readouterr()

    assert result == 0
    assert "publish: would sign and publish this payload" in captured.out
    assert '"kind": 33301' in captured.out


def test_publish_rejects_invalid_json_from_stdin(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO("{not-json"))

    result = run_publish(Namespace(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_JSON


def test_publish_rejects_payload_missing_required_fields(monkeypatch, capsys) -> None:
    payload = {"artifact_version": 1, "event": {"kind": 33301}}
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))

    result = run_publish(Namespace(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert any(err["code"] == MISSING_REQUIRED_FIELD for err in output["errors"])


def test_subscribe_stub_message(capsys) -> None:
    result = run_subscribe(Namespace())
    captured = capsys.readouterr()

    assert result == 0
    assert "subscribe: would connect to relays and stream matching events." in captured.out


def test_main_dispatches_build(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["openprints-cli", "build"])
    result = main()
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert payload["artifact_version"] == 1


def test_publish_rejects_empty_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    result = run_publish(Namespace(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_JSON
    assert "empty" in output["errors"][0]["message"]


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
