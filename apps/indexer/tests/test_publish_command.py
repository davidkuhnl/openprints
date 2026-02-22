import json
import sys
from argparse import Namespace
from io import StringIO
from pathlib import Path

from openprints_cli.commands.publish import run_publish
from openprints_cli.error_codes import INVALID_JSON, MISSING_REQUIRED_FIELD
from tests.test_helpers import valid_draft_payload


def test_publish_reads_payload_from_file(tmp_path: Path, capsys) -> None:
    input_file = tmp_path / "payload.json"
    input_file.write_text(
        json.dumps(valid_draft_payload()),
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
        StringIO(json.dumps(valid_draft_payload())),
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


def test_publish_rejects_empty_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    result = run_publish(Namespace(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_JSON
    assert "empty" in output["errors"][0]["message"]
