import json
import sys
from argparse import Namespace
from pathlib import Path

from openprints_cli.errors import invalid_json, invalid_value
from openprints_cli.payload_contract import validate_payload
from openprints_cli.signers.base import SignerError
from openprints_cli.signers.factory import build_signer


def _read_input(input_value: str) -> str:
    if input_value == "-":
        return sys.stdin.read()
    return Path(input_value).read_text(encoding="utf-8")


def run_sign(args: Namespace) -> int:
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

    state = payload.get("meta", {}).get("state")
    if state != "draft":
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_value("meta.state", "sign expects a draft payload")],
                },
                indent=2,
            )
        )
        return 1

    try:
        signer = build_signer(args.signer, args.nsec_env)
        signed_event = signer.sign_event(payload["event"])
    except SignerError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [invalid_value("signer", str(exc))],
                },
                indent=2,
            )
        )
        return 1

    signed_payload = dict(payload)
    signed_payload["meta"] = dict(payload["meta"])
    signed_payload["meta"]["state"] = "signed"
    signed_payload["event"] = signed_event

    signed_errors = validate_payload(signed_payload)
    if signed_errors:
        print(json.dumps({"ok": False, "errors": signed_errors}, indent=2))
        return 1

    print(json.dumps(signed_payload, indent=2))
    print(f"sign: signed payload using signer backend '{args.signer}'.", file=sys.stderr)
    return 0
