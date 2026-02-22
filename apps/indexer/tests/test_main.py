import json
import sys

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
    assert "hash" in captured.out


def test_main_dispatches_build(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["openprints-cli", "build"])
    result = main()
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert payload["artifact_version"] == 1
