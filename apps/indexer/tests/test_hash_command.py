from __future__ import annotations

from argparse import Namespace
from io import BytesIO, TextIOWrapper
from pathlib import Path

from openprints.cli.commands.hash import run_hash
from openprints.common.utils.sha256 import sha256_file


def test_hash_file_matches_fixture_digest(capsys) -> None:
    fixture = Path(__file__).parent / "fixtures" / "stub_design.stl"
    result = run_hash(Namespace(file=str(fixture)))
    captured = capsys.readouterr()

    assert result == 0
    assert (
        captured.out.strip() == "fc1b7cc223d252f88ddf568a83fe5a446a21d9358cb69cb3d6374c181cc4f3cd"
    )


def test_hash_stdin_binary(monkeypatch, capsys) -> None:
    stdin_stream = TextIOWrapper(BytesIO(b"hello"), encoding="utf-8")
    monkeypatch.setattr("sys.stdin", stdin_stream)

    result = run_hash(Namespace(file="-"))
    captured = capsys.readouterr()

    assert result == 0
    assert (
        captured.out.strip() == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_hash_helper_sha256_file() -> None:
    fixture = Path(__file__).parent / "fixtures" / "stub_design.stl"
    assert (
        sha256_file(fixture) == "fc1b7cc223d252f88ddf568a83fe5a446a21d9358cb69cb3d6374c181cc4f3cd"
    )
