import json
import sys
from argparse import Namespace
from io import StringIO
from pathlib import Path

from bech32 import bech32_encode, convertbits

from openprints.cli.commands.sign import run_sign
from openprints.common.error_codes import INVALID_JSON, INVALID_VALUE
from tests.test_helpers import valid_draft_payload


def _nsec_from_secret_hex(secret_hex: str) -> str:
    data = convertbits(bytes.fromhex(secret_hex), 8, 5, True)
    assert data is not None
    return bech32_encode("nsec", data)


def _args(**overrides: object) -> Namespace:
    base = {
        "input": "-",
        "signer": "dev-nsec",
        "nsec_env": "OPENPRINTS_DEV_NSEC",
    }
    base.update(overrides)
    return Namespace(**base)


def test_sign_reads_payload_from_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv(
        "OPENPRINTS_DEV_NSEC",
        _nsec_from_secret_hex("10" * 32),
    )
    input_file = tmp_path / "payload.json"
    input_file.write_text(
        json.dumps(valid_draft_payload()),
        encoding="utf-8",
    )
    result = run_sign(_args(input=str(input_file)))
    captured = capsys.readouterr()

    assert result == 0
    output = json.loads(captured.out)
    assert output["meta"]["state"] == "signed"
    assert "id" in output["event"]
    assert "sig" in output["event"]
    assert "pubkey" in output["event"]
    assert "sign: signed payload using signer backend 'dev-nsec'." in captured.err


def test_sign_reads_payload_from_stdin(monkeypatch, capsys) -> None:
    monkeypatch.setenv(
        "OPENPRINTS_DEV_NSEC",
        _nsec_from_secret_hex("11" * 32),
    )
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_draft_payload())))

    result = run_sign(_args(input="-"))
    captured = capsys.readouterr()

    assert result == 0
    output = json.loads(captured.out)
    assert output["meta"]["state"] == "signed"
    assert output["event"]["kind"] == 33301


def test_sign_rejects_empty_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    result = run_sign(_args(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_JSON


def test_sign_rejects_invalid_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO("{not-json"))

    result = run_sign(_args(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_JSON


def test_sign_rejects_non_draft_payload(monkeypatch, capsys) -> None:
    payload = valid_draft_payload()
    payload["meta"]["state"] = "signed"
    payload["event"]["id"] = "0" * 64
    payload["event"]["sig"] = "1" * 128
    payload["event"]["pubkey"] = "2" * 64
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))

    result = run_sign(_args(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE


def test_sign_rejects_missing_nsec_env(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENPRINTS_DEV_NSEC", raising=False)
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_draft_payload())))

    result = run_sign(_args(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE


def test_sign_rejects_remote_signer_stub(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_draft_payload())))

    result = run_sign(_args(input="-", signer="remote"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE


def test_sign_is_deterministic_for_same_input(monkeypatch, capsys) -> None:
    monkeypatch.setenv(
        "OPENPRINTS_DEV_NSEC",
        _nsec_from_secret_hex("12" * 32),
    )
    payload = json.dumps(valid_draft_payload())

    monkeypatch.setattr(sys, "stdin", StringIO(payload))
    result_first = run_sign(_args(input="-"))
    captured_first = capsys.readouterr()

    monkeypatch.setattr(sys, "stdin", StringIO(payload))
    result_second = run_sign(_args(input="-"))
    captured_second = capsys.readouterr()

    assert result_first == 0
    assert result_second == 0
    output_first = json.loads(captured_first.out)
    output_second = json.loads(captured_second.out)
    assert output_first["event"]["id"] == output_second["event"]["id"]
    assert output_first["event"]["sig"] == output_second["event"]["sig"]
