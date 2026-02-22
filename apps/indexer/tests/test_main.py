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
    assert "sign" in captured.out
    assert "publish" in captured.out
    assert "subscribe" in captured.out
    assert "hash" in captured.out
    assert "keygen" in captured.out


def test_main_dispatches_build(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "openprints-cli",
            "build",
            "--name",
            "Stub Design",
            "--format",
            "stl",
            "--url",
            "https://example.invalid/stub.stl",
            "--sha256",
            "fc1b7cc223d252f88ddf568a83fe5a446a21d9358cb69cb3d6374c181cc4f3cd",
        ],
    )
    result = main()
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert payload["artifact_version"] == 1
