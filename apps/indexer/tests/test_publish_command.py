import asyncio
import json
import sys
from argparse import Namespace
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import openprints_cli.commands.publish as publish_cmd
from openprints_cli.commands.publish import _publish_event_to_relay, run_publish
from openprints_cli.error_codes import INVALID_JSON, INVALID_VALUE, MISSING_REQUIRED_FIELD
from tests.test_helpers import valid_draft_payload, valid_signed_payload


def _args(**overrides: object) -> Namespace:
    base = {"input": "-", "relay": None, "timeout": 8.0, "retries": 0, "retry_backoff_ms": 0}
    base.update(overrides)
    return Namespace(**base)


async def _publish_success(relay: str, event: dict, timeout: float) -> dict[str, object]:
    return {
        "relay": relay,
        "event_id": event["id"],
        "accepted": True,
        "message": "ok",
    }


def test_publish_reads_payload_from_file(tmp_path: Path, monkeypatch, capsys) -> None:
    input_file = tmp_path / "payload.json"
    input_file.write_text(
        json.dumps(valid_signed_payload()),
        encoding="utf-8",
    )
    monkeypatch.setattr(publish_cmd, "_publish_event_to_relay", _publish_success)

    result = run_publish(_args(input=str(input_file), relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result == 0
    output = json.loads(captured.out)
    assert output["ok"] is True
    assert output["relay_results"][0]["relay"] == "ws://localhost:7447"


def test_publish_reads_payload_from_stdin(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "stdin",
        StringIO(json.dumps(valid_signed_payload())),
    )
    monkeypatch.setattr(publish_cmd, "_publish_event_to_relay", _publish_success)

    result = run_publish(_args(input="-", relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result == 0
    output = json.loads(captured.out)
    assert output["ok"] is True
    assert output["relay_results"][0]["event_id"] == valid_signed_payload()["event"]["id"]


def test_publish_rejects_invalid_json_from_stdin(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO("{not-json"))

    result = run_publish(_args(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_JSON


def test_publish_rejects_payload_missing_required_fields(monkeypatch, capsys) -> None:
    payload = {"artifact_version": 1, "event": {"kind": 33301}}
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))

    result = run_publish(_args(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert any(err["code"] == MISSING_REQUIRED_FIELD for err in output["errors"])


def test_publish_rejects_draft_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_draft_payload())))

    result = run_publish(_args(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE
    assert output["errors"][0]["path"] == "meta.state"


def test_publish_rejects_invalid_signature(monkeypatch, capsys) -> None:
    payload = valid_signed_payload()
    payload["event"]["id"] = "f" * 64  # tamper id so it no longer matches signature
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))

    result = run_publish(_args(input="-", relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["path"] == "event"
    assert "id mismatch" in output["errors"][0]["message"]


def test_publish_rejects_empty_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    result = run_publish(_args(input="-"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_JSON
    assert "empty" in output["errors"][0]["message"]


def test_publish_uses_env_relay_url(monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENPRINTS_RELAY_URL", "ws://env-relay:7447")
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_signed_payload())))
    monkeypatch.setattr(publish_cmd, "_publish_event_to_relay", _publish_success)

    result = run_publish(_args(input="-"))
    captured = capsys.readouterr()

    assert result == 0
    output = json.loads(captured.out)
    assert output["relay_results"][0]["relay"] == "ws://env-relay:7447"


def test_publish_uses_first_openprints_relay_urls_entry(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENPRINTS_RELAY_URL", raising=False)
    monkeypatch.setenv("OPENPRINTS_RELAY_URLS", "ws://first:7447,ws://second:7447")
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_signed_payload())))
    monkeypatch.setattr(publish_cmd, "_publish_event_to_relay", _publish_success)

    result = run_publish(_args(input="-"))
    captured = capsys.readouterr()

    assert result == 0
    output = json.loads(captured.out)
    assert output["relay_results"][0]["relay"] == "ws://first:7447"


def test_publish_rejects_invalid_relay_url(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_signed_payload())))

    result = run_publish(_args(input="-", relay="http://localhost:7447"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE
    assert output["errors"][0]["path"] == "relay"


def test_publish_relay_rejection_returns_machine_readable_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_signed_payload())))

    async def _publish_rejected(relay: str, event: dict, timeout: float) -> dict[str, object]:
        return {
            "relay": relay,
            "event_id": event["id"],
            "accepted": False,
            "message": "blocked: duplicate event",
        }

    monkeypatch.setattr(publish_cmd, "_publish_event_to_relay", _publish_rejected)

    result = run_publish(_args(input="-", relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE
    assert output["relay_results"][0]["accepted"] is False


def test_publish_transport_exception_returns_machine_readable_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_signed_payload())))

    async def _boom(relay, event, timeout):
        raise RuntimeError("connect failed")

    monkeypatch.setattr(publish_cmd, "_publish_event_to_relay", _boom)

    result = run_publish(_args(input="-", relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE
    assert "connect failed" in output["errors"][0]["message"]


def test_publish_retries_transport_error_then_succeeds(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_signed_payload())))
    calls = {"count": 0}

    async def _flaky(relay, event, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary connect failure")
        return {
            "relay": relay,
            "event_id": event["id"],
            "accepted": True,
            "message": "ok",
        }

    monkeypatch.setattr(publish_cmd, "_publish_event_to_relay", _flaky)

    result = run_publish(
        _args(input="-", relay="ws://localhost:7447", retries=1, retry_backoff_ms=0)
    )
    captured = capsys.readouterr()

    assert result == 0
    output = json.loads(captured.out)
    assert output["ok"] is True
    assert calls["count"] == 2


def test_publish_does_not_retry_on_ok_false(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(valid_signed_payload())))
    calls = {"count": 0}

    async def _relay_reject(relay, event, timeout):
        calls["count"] += 1
        return {
            "relay": relay,
            "event_id": event["id"],
            "accepted": False,
            "message": "blocked: duplicate event",
        }

    monkeypatch.setattr(publish_cmd, "_publish_event_to_relay", _relay_reject)

    result = run_publish(
        _args(input="-", relay="ws://localhost:7447", retries=3, retry_backoff_ms=0)
    )
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert calls["count"] == 1


def test_publish_event_to_relay_success() -> None:
    event = valid_signed_payload()["event"]
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(
        return_value=json.dumps(["OK", event["id"], True, "ok"], separators=(",", ":"))
    )

    class MockConnect:
        async def __aenter__(self) -> MagicMock:
            return mock_ws

        async def __aexit__(self, *args: object) -> None:
            pass

    with patch("openprints_cli.commands.publish.websockets.connect", return_value=MockConnect()):
        result = asyncio.run(_publish_event_to_relay("ws://localhost:7447", event, timeout_s=1.0))
    assert result["accepted"] is True
    assert result["event_id"] == event["id"]
    assert result["relay"] == "ws://localhost:7447"


def test_publish_event_to_relay_non_json_response() -> None:
    event = valid_signed_payload()["event"]
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(return_value="not json")

    class MockConnect:
        async def __aenter__(self) -> MagicMock:
            return mock_ws

        async def __aexit__(self, *args: object) -> None:
            pass

    with patch("openprints_cli.commands.publish.websockets.connect", return_value=MockConnect()):
        result = asyncio.run(_publish_event_to_relay("ws://localhost:7447", event, timeout_s=1.0))
    assert result["accepted"] is False
    assert "non-JSON" in result["message"] or "not json" in result["message"]


def test_publish_event_to_relay_unexpected_response() -> None:
    event = valid_signed_payload()["event"]
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(
        return_value=json.dumps(["NOT_OK", "id", "bad"], separators=(",", ":"))
    )

    class MockConnect:
        async def __aenter__(self) -> MagicMock:
            return mock_ws

        async def __aexit__(self, *args: object) -> None:
            pass

    with patch("openprints_cli.commands.publish.websockets.connect", return_value=MockConnect()):
        result = asyncio.run(_publish_event_to_relay("ws://localhost:7447", event, timeout_s=1.0))
    assert result["accepted"] is False
    assert "unexpected" in result["message"].lower()
