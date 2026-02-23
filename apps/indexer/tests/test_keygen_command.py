import json
from argparse import Namespace

from openprints.cli.commands.keygen import run_keygen


def _args(**overrides: object) -> Namespace:
    base = {
        "json": False,
        "env": False,
        "env_name": "OPENPRINTS_DEV_NSEC",
    }
    base.update(overrides)
    return Namespace(**base)


def test_keygen_default_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "openprints.cli.commands.keygen.secrets.token_bytes", lambda _n: b"\x11" * 32
    )

    result = run_keygen(_args())
    captured = capsys.readouterr()

    assert result == 0
    assert "Generated dev keypair:" in captured.out
    assert "nsec:" in captured.out
    assert "npub:" in captured.out
    assert "pubkey:" in captured.out
    assert "OPENPRINTS_DEV_NSEC=nsec1" in captured.out
    assert "do not commit or share private keys" in captured.err


def test_keygen_json_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "openprints.cli.commands.keygen.secrets.token_bytes", lambda _n: b"\x22" * 32
    )

    result = run_keygen(_args(json=True))
    captured = capsys.readouterr()

    assert result == 0
    output = json.loads(captured.out)
    assert output["nsec"].startswith("nsec1")
    assert output["npub"].startswith("npub1")
    assert len(output["pubkey"]) == 64
    assert output["env_var"] == "OPENPRINTS_DEV_NSEC"


def test_keygen_env_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "openprints.cli.commands.keygen.secrets.token_bytes", lambda _n: b"\x33" * 32
    )

    result = run_keygen(_args(env=True, env_name="MY_DEV_NSEC"))
    captured = capsys.readouterr()

    assert result == 0
    assert captured.out.strip().startswith("MY_DEV_NSEC=nsec1")
