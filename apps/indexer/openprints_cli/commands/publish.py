import json
import sys
from argparse import Namespace
from pathlib import Path

from openprints_cli.errors import invalid_json
from openprints_cli.payload_contract import validate_payload


def _read_input(input_value: str) -> str:
    if input_value == "-":
        return sys.stdin.read()
    return Path(input_value).read_text(encoding="utf-8")


def run_publish(args: Namespace) -> int:
    raw_payload = _read_input(args.input)
    if not raw_payload.strip():
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_json("$", "input is empty")],
                },
                indent=2,
            )
        )
        return 1

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_json("$", f"input is not valid JSON ({exc})")],
                },
                indent=2,
            )
        )
        return 1

    errors = validate_payload(payload)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1

    print("publish: would sign and publish this payload to configured relays:")
    print(json.dumps(payload, indent=2))
    return 0
