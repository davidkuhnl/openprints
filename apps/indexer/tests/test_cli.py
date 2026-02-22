import json
import sys
from argparse import Namespace
from io import StringIO
from pathlib import Path

from openprints_cli.commands.build import run_build
from openprints_cli.commands.publish import run_publish
from openprints_cli.main import main


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
    assert payload["event"]["kind"] == 33301
    assert f"build: wrote payload JSON to {output_file}." in captured.out


def test_publish_reads_payload_from_file(tmp_path: Path, capsys) -> None:
    input_file = tmp_path / "payload.json"
    input_file.write_text(
        json.dumps({"artifact_version": 1, "event": {"kind": 33301}}),
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
        StringIO(json.dumps({"artifact_version": 1, "event": {"kind": 33301}})),
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
    assert "publish: input is not valid JSON" in captured.out
