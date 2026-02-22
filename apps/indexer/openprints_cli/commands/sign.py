import json
import sys
from argparse import Namespace

from openprints_cli.errors import invalid_json, invalid_value
from openprints_cli.payload_contract import validate_payload
from openprints_cli.signers.base import SignerError
from openprints_cli.signers.factory import build_signer
from openprints_cli.utils.input import read_text_input
from openprints_cli.utils.output import print_json


def run_sign(args: Namespace) -> int:
    raw_payload = read_text_input(args.input)
    if not raw_payload.strip():
        print_json({"ok": False, "errors": [invalid_json("$", "input is empty")]})
        return 1

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        print_json({"ok": False, "errors": [invalid_json("$", f"input is not valid JSON ({exc})")]})
        return 1

    errors = validate_payload(payload)
    if errors:
        print_json({"ok": False, "errors": errors})
        return 1

    state = payload.get("meta", {}).get("state")
    if state != "draft":
        print_json(
            {
                "ok": False,
                "errors": [invalid_value("meta.state", "sign expects a draft payload")],
            }
        )
        return 1

    try:
        signer = build_signer(args.signer, args.nsec_env)
        signed_event = signer.sign_event(payload["event"])
    except SignerError as exc:
        print_json({"ok": False, "errors": [invalid_value("signer", str(exc))]})
        return 1

    signed_payload = dict(payload)
    signed_payload["meta"] = dict(payload["meta"])
    signed_payload["meta"]["state"] = "signed"
    signed_payload["event"] = signed_event

    signed_errors = validate_payload(signed_payload)
    if signed_errors:
        print_json({"ok": False, "errors": signed_errors})
        return 1

    print_json(signed_payload)
    print(f"sign: signed payload using signer backend '{args.signer}'.", file=sys.stderr)
    return 0
