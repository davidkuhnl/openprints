import asyncio
import json
from argparse import Namespace

from websockets.exceptions import ConnectionClosedOK

import openprints_cli.commands.subscribe as subscribe_cmd
from openprints_cli.commands.subscribe import run_subscribe
from openprints_cli.error_codes import INVALID_VALUE


def _args(**overrides: object) -> Namespace:
    base = {"relay": None, "kind": 33301, "limit": 1, "timeout": 8.0}
    base.update(overrides)
    return Namespace(**base)


def test_subscribe_returns_ok_summary(monkeypatch, capsys) -> None:
    async def _fake_subscribe_once(
        relay: str, kind: int, timeout_s: float, limit: int
    ) -> dict[str, object]:
        return {"relay": relay, "events_seen": 1, "eose_seen": True}

    monkeypatch.setattr(subscribe_cmd, "_subscribe_once", _fake_subscribe_once)

    result = run_subscribe(_args(relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result == 0
    summary = json.loads(captured.err)
    assert summary["ok"] is True
    assert summary["relay_results"][0]["events_seen"] == 1


def test_subscribe_rejects_invalid_relay() -> None:
    result = run_subscribe(_args(relay="http://localhost:7447"))
    assert result != 0


def test_subscribe_transport_error_returns_machine_error(monkeypatch, capsys) -> None:
    async def _boom(relay: str, kind: int, timeout_s: float, limit: int) -> dict[str, object]:
        raise RuntimeError("connect failed")

    monkeypatch.setattr(subscribe_cmd, "_subscribe_once", _boom)

    result = run_subscribe(_args(relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result != 0
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["errors"][0]["code"] == INVALID_VALUE
    assert "connect failed" in output["errors"][0]["message"]


def test_subscribe_connection_closed_is_graceful(monkeypatch, capsys) -> None:
    async def _closed(relay: str, kind: int, timeout_s: float, limit: int) -> dict[str, object]:
        raise ConnectionClosedOK(None, None)

    monkeypatch.setattr(subscribe_cmd, "_subscribe_once", _closed)

    result = run_subscribe(_args(relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result == 0
    summary = json.loads(captured.err)
    assert summary["ok"] is True
    assert summary["relay_results"][0]["status"] == "disconnected"


def test_subscribe_keyboard_interrupt_is_graceful(monkeypatch, capsys) -> None:
    async def _interrupt(relay: str, kind: int, timeout_s: float, limit: int) -> dict[str, object]:
        raise KeyboardInterrupt()

    monkeypatch.setattr(subscribe_cmd, "_subscribe_once", _interrupt)

    result = run_subscribe(_args(relay="ws://localhost:7447"))
    captured = capsys.readouterr()

    assert result == 0
    summary = json.loads(captured.err)
    assert summary["ok"] is True
    assert summary["relay_results"][0]["status"] == "interrupted"


class _FakeWebSocket:
    def __init__(self, recv_items: list[object]) -> None:
        self.recv_items = recv_items
        self.sent: list[str] = []

    async def __aenter__(self) -> "_FakeWebSocket":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def send(self, value: str) -> None:
        self.sent.append(value)

    async def recv(self) -> str:
        if not self.recv_items:
            raise asyncio.TimeoutError()
        item = self.recv_items.pop(0)
        if isinstance(item, Exception):
            raise item
        return str(item)


def test_subscribe_once_streams_event_and_closes_on_limit(monkeypatch) -> None:
    sub_id = "openprints-cli-fixed"
    fake_ws = _FakeWebSocket(
        recv_items=[
            json.dumps(["EVENT", sub_id, {"id": "a" * 64, "kind": 33301}]),
        ]
    )
    monkeypatch.setattr(subscribe_cmd.secrets, "token_hex", lambda _n: "fixed")
    monkeypatch.setattr(subscribe_cmd.websockets, "connect", lambda *args, **kwargs: fake_ws)

    result = asyncio.run(
        subscribe_cmd._subscribe_once(
            relay="ws://localhost:7447",
            kind=33301,
            timeout_s=1.0,
            limit=1,
        )
    )

    assert result["events_seen"] == 1
    assert result["eose_seen"] is False
    assert any('"REQ"' in sent for sent in fake_ws.sent)
    assert any('"CLOSE"' in sent for sent in fake_ws.sent)


def test_subscribe_once_handles_notice_malformed_and_eose(monkeypatch, capsys) -> None:
    sub_id = "openprints-cli-fixed"
    fake_ws = _FakeWebSocket(
        recv_items=[
            json.dumps(["NOTICE", "slow relay"]),
            "not-json",
            json.dumps(["EOSE", sub_id]),
        ]
    )
    monkeypatch.setattr(subscribe_cmd.secrets, "token_hex", lambda _n: "fixed")
    monkeypatch.setattr(subscribe_cmd.websockets, "connect", lambda *args, **kwargs: fake_ws)

    result = asyncio.run(
        subscribe_cmd._subscribe_once(
            relay="ws://localhost:7447",
            kind=33301,
            timeout_s=1.0,
            limit=0,
        )
    )
    captured = capsys.readouterr()

    assert result["events_seen"] == 0
    assert result["eose_seen"] is True
    assert "NOTICE" in captured.err
    assert "MALFORMED" in captured.err


def test_subscribe_once_limit_zero_continues_after_eose_until_timeout(monkeypatch, capsys) -> None:
    sub_id = "openprints-cli-fixed"
    fake_ws = _FakeWebSocket(
        recv_items=[
            json.dumps(["EOSE", sub_id]),
            json.dumps(["EVENT", sub_id, {"id": "b" * 64, "kind": 33301}]),
            asyncio.TimeoutError(),
        ]
    )
    monkeypatch.setattr(subscribe_cmd.secrets, "token_hex", lambda _n: "fixed")
    monkeypatch.setattr(subscribe_cmd.websockets, "connect", lambda *args, **kwargs: fake_ws)

    result = asyncio.run(
        subscribe_cmd._subscribe_once(
            relay="ws://localhost:7447",
            kind=33301,
            timeout_s=1.0,
            limit=0,
        )
    )
    captured = capsys.readouterr()

    assert result["events_seen"] == 1
    assert result["eose_seen"] is True
    assert '"id":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"' in captured.out


def test_subscribe_resolve_relay_url_fallbacks(monkeypatch) -> None:
    monkeypatch.delenv("OPENPRINTS_RELAY_URL", raising=False)
    monkeypatch.delenv("OPENPRINTS_RELAY_URLS", raising=False)
    relay, errors = subscribe_cmd.resolve_relay_url(_args())
    assert errors == []
    assert relay == "ws://localhost:7447"

    monkeypatch.setenv("OPENPRINTS_RELAY_URL", "ws://env-relay:7447")
    relay, errors = subscribe_cmd.resolve_relay_url(_args())
    assert errors == []
    assert relay == "ws://env-relay:7447"

    monkeypatch.delenv("OPENPRINTS_RELAY_URL", raising=False)
    monkeypatch.setenv("OPENPRINTS_RELAY_URLS", "ws://first:7447,ws://second:7447")
    relay, errors = subscribe_cmd.resolve_relay_url(_args())
    assert errors == []
    assert relay == "ws://first:7447"
