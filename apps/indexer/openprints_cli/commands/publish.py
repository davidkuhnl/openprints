import json
import sys
from argparse import Namespace
from pathlib import Path


def _read_input(input_value: str) -> str:
    if input_value == "-":
        return sys.stdin.read()
    return Path(input_value).read_text(encoding="utf-8")


def run_publish(args: Namespace) -> int:
    raw_payload = _read_input(args.input)
    if not raw_payload.strip():
        print("publish: no payload provided (empty input).")
        return 1

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        print(f"publish: input is not valid JSON ({exc}).")
        return 1

    print("publish: would sign and publish this payload to configured relays:")
    print(json.dumps(payload, indent=2))
    return 0
