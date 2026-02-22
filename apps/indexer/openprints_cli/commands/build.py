import json
import sys
import time
from argparse import Namespace
from pathlib import Path

from openprints_cli.payload_contract import ARTIFACT_VERSION, validate_payload


def _placeholder_payload() -> dict:
    return {
        "artifact_version": ARTIFACT_VERSION,
        "meta": {
            "state": "draft",
            "source": "openprints-cli",
        },
        "event": {
            "kind": 33301,
            "created_at": int(time.time()),
            "tags": [
                ["d", "openprints:stub-design-id"],
                ["name", "Stub Design"],
                ["format", "stl"],
                ["sha256", "0000000000000000000000000000000000000000000000000000000000000000"],
                ["url", "https://example.invalid/stub.stl"],
            ],
            "content": "Stub payload from openprints-cli build.",
        },
    }


def run_build(args: Namespace) -> int:
    payload = _placeholder_payload()
    errors = validate_payload(payload)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2), file=sys.stderr)
        return 1

    serialized = json.dumps(payload, indent=2)

    if args.output == "-":
        print(serialized)
        print("build: wrote payload JSON to stdout.", file=sys.stderr)
        return 0

    output_path = Path(args.output)
    output_path.write_text(serialized + "\n", encoding="utf-8")
    print(f"build: wrote payload JSON to {output_path}.")
    return 0
