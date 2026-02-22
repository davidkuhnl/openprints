from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from openprints_cli.utils.hash import sha256_bytes, sha256_file


def run_hash(args: Namespace) -> int:
    if args.file == "-":
        if hasattr(sys.stdin, "buffer"):
            data = sys.stdin.buffer.read()
        else:
            data = sys.stdin.read().encode("utf-8")
        print(sha256_bytes(data))
        return 0

    try:
        digest = sha256_file(Path(args.file))
    except OSError as exc:
        print(f"hash: failed to read {args.file}: {exc}", file=sys.stderr)
        return 1

    print(digest)
    return 0
