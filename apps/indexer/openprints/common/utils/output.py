from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def serialize_json(
    payload: Any,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = True,
    compact: bool = False,
) -> str:
    if compact:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=ensure_ascii)
    return json.dumps(payload, indent=indent, ensure_ascii=ensure_ascii)


def print_json(
    payload: Any,
    *,
    stream: TextIO | None = None,
    indent: int | None = 2,
    ensure_ascii: bool = True,
    compact: bool = False,
) -> None:
    output_stream = stream or sys.stdout
    print(
        serialize_json(
            payload,
            indent=indent,
            ensure_ascii=ensure_ascii,
            compact=compact,
        ),
        file=output_stream,
    )
