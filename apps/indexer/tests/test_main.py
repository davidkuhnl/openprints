import json
import runpy
import sys

import pytest

from openprints.cli.main import main


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
    assert "index" in captured.out
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


def test___main___exits_zero_with_help(monkeypatch, capsys) -> None:
    """Running python -m openprints --help exits 0 and prints help."""
    monkeypatch.setattr(sys, "argv", ["openprints-cli", "--help"])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("openprints", run_name="__main__")
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "openprints-cli" in out
    assert "index" in out
