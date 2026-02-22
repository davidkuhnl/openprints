from argparse import Namespace

from openprints_cli.commands.subscribe import run_subscribe


def test_subscribe_stub_message(capsys) -> None:
    result = run_subscribe(Namespace())
    captured = capsys.readouterr()

    assert result == 0
    assert "subscribe: would connect to relays and stream matching events." in captured.out
