"""Append-only evidence ledger: SQLite for records, content-addressed files for raw evidence.

Each entry's hash covers the previous entry's hash, so editing, removing or reordering an
entry by going around this API is detected by `verify`. Truncating the newest entries is not
detectable from the ledger alone; keep `head_hash` elsewhere (the report prints it) for that.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from .. import schemas
from ..schemas import StoredRecord
from .hashing import canonical_json, sha256_bytes, sha256_file

_KINDS: dict[str, type[StoredRecord]] = {
    cls.__name__: cls
    for cls in (
        schemas.AuditInfo,
        schemas.Claim,
        schemas.ExperimentSpec,
        schemas.ArtifactRecord,
        schemas.ConsistencyFinding,
        schemas.Approval,
        schemas.RunRecord,
        schemas.MetricObservation,
        schemas.IntegrityCheck,
        schemas.Verdict,
    )
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    seq        INTEGER PRIMARY KEY,
    id         TEXT NOT NULL UNIQUE,
    kind       TEXT NOT NULL,
    body       TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (sha256 TEXT PRIMARY KEY, size INTEGER NOT NULL);
CREATE TRIGGER IF NOT EXISTS records_no_update BEFORE UPDATE ON records
    BEGIN SELECT RAISE(ABORT, 'the ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS records_no_delete BEFORE DELETE ON records
    BEGIN SELECT RAISE(ABORT, 'the ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS files_no_update BEFORE UPDATE ON files
    BEGIN SELECT RAISE(ABORT, 'the ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS files_no_delete BEFORE DELETE ON files
    BEGIN SELECT RAISE(ABORT, 'the ledger is append-only'); END;
"""

_GENESIS = "0" * 64


class LedgerError(Exception):
    pass


def _entry_hash(previous: str, id_: str, kind: str, body: str) -> str:
    return sha256_bytes("\n".join((previous, id_, kind, body)).encode("utf-8"))


class Ledger:
    def __init__(self, root: Path) -> None:
        self._files = root / "files"
        self._files.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(root / "ledger.sqlite")
        self._db.executescript(_SCHEMA)

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    @property
    def head_hash(self) -> str:
        row = self._db.execute(
            "SELECT entry_hash FROM records ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else _GENESIS

    def add(self, record: StoredRecord) -> None:
        kind = type(record).__name__
        if _KINDS.get(kind) is not type(record):
            raise LedgerError(f"not a ledger record: {kind}")
        body = canonical_json(record)
        try:
            with self._db:
                self._db.execute(
                    "INSERT INTO records (id, kind, body, entry_hash) VALUES (?, ?, ?, ?)",
                    (record.id, kind, body, _entry_hash(self.head_hash, record.id, kind, body)),
                )
        except sqlite3.IntegrityError as e:
            raise LedgerError(f"record {record.id!r} already exists") from e

    def get(self, id_: str) -> StoredRecord:
        row = self._db.execute("SELECT kind, body FROM records WHERE id = ?", (id_,)).fetchone()
        if row is None:
            raise LedgerError(f"no record {id_!r}")
        return _KINDS[row[0]].model_validate_json(row[1])

    def records(self, kind: type[StoredRecord] | None = None) -> list[StoredRecord]:
        rows = self._db.execute("SELECT kind, body FROM records ORDER BY seq").fetchall()
        return [
            _KINDS[k].model_validate_json(body)
            for k, body in rows
            if kind is None or k == kind.__name__
        ]

    def add_file(self, path: Path, expected_sha256: str | None = None) -> str:
        """Copy a file in under its own hash, so later changes to it are detectable."""
        digest = sha256_file(path)
        if expected_sha256 is not None and digest != expected_sha256:
            raise LedgerError(f"{path.name}: content does not match its recorded hash")
        target = self.file_path(digest)
        if not target.exists():
            shutil.copyfile(path, target)
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO files (sha256, size) VALUES (?, ?)",
                (digest, target.stat().st_size),
            )
        return digest

    def file_path(self, digest: str) -> Path:
        return self._files / digest

    def verify(self) -> list[str]:
        """Return every integrity problem found; an empty list means none."""
        problems = []
        previous = _GENESIS
        for id_, kind, body, stored in self._db.execute(
            "SELECT id, kind, body, entry_hash FROM records ORDER BY seq"
        ):
            if _entry_hash(previous, id_, kind, body) != stored:
                problems.append(f"record {id_}: hash chain broken")
            previous = stored
        for (digest,) in self._db.execute("SELECT sha256 FROM files"):
            path = self.file_path(digest)
            if not path.exists():
                problems.append(f"file {digest}: missing")
            elif sha256_file(path) != digest:
                problems.append(f"file {digest}: content changed")
        return problems
