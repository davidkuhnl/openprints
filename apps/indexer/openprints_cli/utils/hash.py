from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_reader(reader: BinaryIO, chunk_size: int = 8192) -> str:
    hasher = hashlib.sha256()
    for chunk in iter(lambda: reader.read(chunk_size), b""):
        hasher.update(chunk)
    return hasher.hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as file_obj:
        return sha256_reader(file_obj)
