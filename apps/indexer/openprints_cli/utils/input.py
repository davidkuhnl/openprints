from __future__ import annotations

import sys
from pathlib import Path


def read_text_input(input_value: str) -> str:
    if input_value == "-":
        return sys.stdin.read()
    return Path(input_value).read_text(encoding="utf-8")
