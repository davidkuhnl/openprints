import json
import re
import sys
import time
from argparse import Namespace
from pathlib import Path
from uuid import UUID, uuid4

from openprints_cli.errors import invalid_value
from openprints_cli.payload_contract import ARTIFACT_VERSION, validate_payload
from openprints_cli.utils.hash import sha256_file

SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _normalize_sha256(args: Namespace) -> tuple[str | None, list[dict[str, str]]]:
    if args.sha256 is not None:
        digest = str(args.sha256).strip().lower()
        if not SHA256_HEX_PATTERN.fullmatch(digest):
            return None, [
                invalid_value("sha256", "sha256 must be a 64-character lowercase hex string")
            ]
        return digest, []

    if args.file is not None:
        try:
            return sha256_file(Path(args.file)), []
        except OSError as exc:
            return None, [invalid_value("file", f"unable to read file for hashing: {exc}")]

    return None, [invalid_value("sha256", "either --file or --sha256 is required")]


def _normalize_design_id(raw_value: str | None) -> tuple[str | None, bool, list[dict[str, str]]]:
    generated = raw_value is None
    candidate = raw_value or str(uuid4())
    if candidate.startswith("openprints:"):
        candidate = candidate[len("openprints:") :]

    try:
        parsed = UUID(candidate)
    except ValueError:
        return None, generated, [invalid_value("design_id", "design_id must be a valid uuid-v4")]

    if parsed.version != 4:
        return None, generated, [invalid_value("design_id", "design_id must be a valid uuid-v4")]

    return f"openprints:{parsed}", generated, []


def _build_draft_payload(args: Namespace) -> tuple[dict | None, bool, list[dict[str, str]]]:
    sha256_value, hash_errors = _normalize_sha256(args)
    if hash_errors:
        return None, False, hash_errors

    design_id_value, design_id_generated, design_id_errors = _normalize_design_id(args.design_id)
    if design_id_errors:
        return None, False, design_id_errors

    return (
        {
            "artifact_version": ARTIFACT_VERSION,
            "meta": {
                "state": "draft",
                "source": "openprints-cli",
            },
            "event": {
                "kind": 33301,
                "created_at": int(time.time()),
                "tags": [
                    ["d", design_id_value],
                    ["name", args.name],
                    ["format", args.format],
                    ["sha256", sha256_value],
                    ["url", args.url],
                ],
                "content": args.content,
            },
        },
        design_id_generated,
        [],
    )


def run_build(args: Namespace) -> int:
    payload, design_id_generated, build_errors = _build_draft_payload(args)
    if build_errors:
        print(json.dumps({"ok": False, "errors": build_errors}, indent=2), file=sys.stderr)
        return 1

    errors = validate_payload(payload)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2), file=sys.stderr)
        return 1

    serialized = json.dumps(payload, indent=2)

    if args.output == "-":
        print(serialized)
        if design_id_generated:
            print("build: generated design id for d tag.", file=sys.stderr)
        print("build: wrote payload JSON to stdout.", file=sys.stderr)
        return 0

    output_path = Path(args.output)
    output_path.write_text(serialized + "\n", encoding="utf-8")
    if design_id_generated:
        print("build: generated design id for d tag.")
    print(f"build: wrote payload JSON to {output_path}.")
    return 0
