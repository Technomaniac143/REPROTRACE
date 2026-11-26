"""Basic "computed, not copied" checks on recorded evidence (Project.md section 7).

None of these is proof alone, and each result says what it cannot show. A check that could
not be done is inconclusive, never a pass.
"""

from __future__ import annotations

import re
import struct
from decimal import Decimal
from pathlib import Path, PurePosixPath

from ..evidence.hashing import sha256_bytes, sha256_file
from ..schemas import (
    CheckName,
    CheckResult,
    Criterion,
    FileEvidence,
    IntegrityCheck,
    MetricObservation,
    RunRecord,
    Unit,
)
from .comparison import convert, to_decimal

REQUIRED_CHECKS = frozenset(CheckName)

MAX_SCAN_BYTES = 50 * 1024 * 1024
# Shorter numbers (0.95, 90) appear in code for unrelated reasons, so a hit proves little.
MIN_SIGNIFICANT_DIGITS = 3
_SOURCE_SUFFIXES = {".py", ".ipynb", ".sh", ".r", ".jl"}


def _representations(value: float, unit: Unit) -> set[Decimal]:
    exact = to_decimal(value)
    found = {exact}
    for other in (Unit.PERCENT, Unit.FRACTION):
        converted = convert(exact, unit, other)
        if converted is not None:
            found.add(converted)
    return found


def _plain(value: Decimal) -> str:
    text = format(abs(value), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _significant_digits(value: Decimal) -> int:
    return len(_plain(value).replace(".", "").lstrip("0"))


def _literal_pattern(value: Decimal) -> re.Pattern[bytes]:
    """Match the number as written, allowing trailing zeros and a bare leading point."""
    whole, _, fraction = _plain(value).partition(".")
    if fraction:
        lead = "0?" if whole == "0" else whole
        body = rf"{lead}\.{fraction}0*"
    else:
        body = rf"{whole}(?:\.0+)?"
    # The tail rejects longer numbers, version strings (94.2.1) and exponents (94.2e-1).
    return re.compile(rf"(?<![\d.]){body}(?!\d)(?!\.\d)(?![eE][+-]?\d)".encode("ascii"))


def _contains(data: bytes, value: Decimal) -> bool:
    if _literal_pattern(value).search(data):
        return True
    scientific = repr(float(value))
    if "e" in scientific and scientific.encode("ascii") in data:
        return True
    # Also catch doubles in uncompressed binary files such as .npy.
    return (
        _significant_digits(value) >= MIN_SIGNIFICANT_DIGITS
        and struct.pack("<d", float(value)) in data
    )


def _check(
    name: CheckName,
    run: RunRecord,
    observation: MetricObservation,
    result: CheckResult,
    evidence: list[str],
    limitation: str,
) -> IntegrityCheck:
    return IntegrityCheck(
        id=f"check:{observation.id}:{name}",
        run_id=run.id,
        observation_id=observation.id,
        name=name,
        result=result,
        evidence=tuple(evidence),
        limitation=limitation,
    )


def recorded_source(run: RunRecord, observation: MetricObservation) -> FileEvidence | None:
    for file in (run.log, *run.outputs):
        if file.path == observation.source_path and file.sha256 == observation.source_sha256:
            return file
    return None


def check_output_created(run: RunRecord, observation: MetricObservation) -> IntegrityCheck:
    def done(result: CheckResult, message: str) -> IntegrityCheck:
        return _check(
            CheckName.OUTPUT_CREATED_DURING_RUN,
            run,
            observation,
            result,
            [message],
            "Relies on file times recorded by the runner. A new file can still hold an old number.",
        )

    source = recorded_source(run, observation)
    if source is None:
        return done(
            CheckResult.INCONCLUSIVE,
            f"{observation.source_path} with this hash is not among the run's recorded files",
        )
    if source.sha256 in {f.sha256 for f in run.input_files}:
        return done(
            CheckResult.FLAGGED, f"{source.path} is identical to a file that existed before the run"
        )
    if source.created_at is None:
        return done(CheckResult.INCONCLUSIVE, f"no creation time recorded for {source.path}")
    if not run.started_at <= source.created_at <= run.ended_at:
        return done(
            CheckResult.FLAGGED,
            f"{source.path} was created at {source.created_at.isoformat()}, outside the run",
        )
    return done(CheckResult.PASS, f"{source.path} was created during the run")


def check_value_in_source(
    run: RunRecord, observation: MetricObservation, source_file: Path
) -> IntegrityCheck:
    def done(result: CheckResult, message: str) -> IntegrityCheck:
        return _check(
            CheckName.VALUE_FOUND_IN_SOURCE,
            run,
            observation,
            result,
            [message],
            "Shows the number is in the file, not that the file reports it for this metric.",
        )

    if observation.value is None:
        return done(CheckResult.INCONCLUSIVE, "the observation has no value")
    if not source_file.is_file() or sha256_file(source_file) != observation.source_sha256:
        return done(
            CheckResult.INCONCLUSIVE,
            f"{observation.source_path} is unavailable or does not match its recorded hash",
        )
    if source_file.stat().st_size > MAX_SCAN_BYTES:
        return done(CheckResult.INCONCLUSIVE, f"{observation.source_path} is too large to scan")
    if _contains(source_file.read_bytes(), to_decimal(observation.value)):
        return done(CheckResult.PASS, f"{observation.value} appears in {observation.source_path}")
    return done(
        CheckResult.FLAGGED, f"{observation.value} does not appear in {observation.source_path}"
    )


def check_value_not_in_inputs(
    run: RunRecord, criterion: Criterion, observation: MetricObservation, inputs_root: Path
) -> IntegrityCheck:
    """Look for the claimed and observed values in files that existed before the run."""
    values = _representations(criterion.expected, criterion.unit)
    if observation.value is not None:
        values |= _representations(observation.value, observation.unit)

    flagged: list[str] = []
    unclear: list[str] = []
    notes: list[str] = []

    if not run.input_files:
        unclear.append("no inventory of files that existed before the run")
    for file in run.input_files:
        is_source = PurePosixPath(file.path).suffix.lower() in _SOURCE_SUFFIXES
        # Source counts even when not seen to be read: read records can miss imports.
        relevant = is_source or run.files_read is None or file.path in run.files_read
        path = inputs_root / file.path
        # A link in an untrusted snapshot must not lead the scan outside it.
        inside = path.resolve().is_relative_to(inputs_root.resolve())
        if not inside or not path.is_file():
            unclear.append(f"{file.path}: not available to scan")
            continue
        if path.stat().st_size > MAX_SCAN_BYTES:
            (unclear if relevant else notes).append(f"{file.path}: too large to scan")
            continue
        data = path.read_bytes()
        if sha256_bytes(data) != file.sha256:
            unclear.append(f"{file.path}: differs from the file recorded before the run")
            continue
        for value in sorted(v for v in values if _contains(data, v)):
            hit = f"{file.path}: contains {_plain(value)}"
            if not relevant:
                notes.append(f"{hit} (not read by the run)")
            elif _significant_digits(value) < MIN_SIGNIFICANT_DIGITS:
                unclear.append(f"{hit}, too few digits to be distinctive")
            elif is_source or run.files_read is not None:
                flagged.append(hit)
            else:
                unclear.append(f"{hit}, and file reads were not recorded")

    if flagged:
        result = CheckResult.FLAGGED
    elif unclear:
        result = CheckResult.INCONCLUSIVE
    else:
        result = CheckResult.PASS
    evidence = flagged + unclear + notes
    return _check(
        CheckName.VALUE_NOT_IN_INPUTS,
        run,
        observation,
        result,
        evidence or [f"{len(run.input_files)} input files scanned, no matching value"],
        "Cannot see inside compressed or encoded files, or a number assembled at run time. "
        "A hit can be coincidental.",
    )


def run_checks(
    run: RunRecord,
    criterion: Criterion,
    observation: MetricObservation,
    *,
    inputs_root: Path,
    source_file: Path,
) -> tuple[IntegrityCheck, ...]:
    return (
        check_output_created(run, observation),
        check_value_in_source(run, observation, source_file),
        check_value_not_in_inputs(run, criterion, observation, inputs_root),
    )
