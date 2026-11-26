"""SHA-256 helpers. Records are hashed over canonical JSON so equal records hash equally."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def canonical_json(record: BaseModel, *, exclude: set[str] | None = None) -> str:
    return json.dumps(
        record.model_dump(mode="json", exclude=exclude),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def record_hash(record: BaseModel, *, exclude: set[str] | None = None) -> str:
    return sha256_bytes(canonical_json(record, exclude=exclude).encode("utf-8"))
