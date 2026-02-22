import json
import sys
import time
from argparse import Namespace
from pathlib import Path


def _placeholder_payload() -> dict:
    return {
        "artifact_version": 1,
        "event": {
            "kind": 33301,
            "created_at": int(time.time()),
            "tags": [
                ["d", "openprints:stub-design-id"],
                ["name", "Stub Design"],
                ["format", "stl"],
                ["sha256", "stub-sha256"],
                ["url", "https://example.invalid/stub.stl"],
            ],
            "content": "Stub payload from openprints-cli build.",
        },
    }


def run_build(args: Namespace) -> int:
    payload = _placeholder_payload()
    serialized = json.dumps(payload, indent=2)

    if args.output == "-":
        print(serialized)
        print("build: wrote payload JSON to stdout.", file=sys.stderr)
        return 0

    output_path = Path(args.output)
    output_path.write_text(serialized + "\n", encoding="utf-8")
    print(f"build: wrote payload JSON to {output_path}.")
    return 0
