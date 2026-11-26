"""Shared records (Project.md section 7).

Records are immutable and reject unknown fields. Anything whose absence would let an
unsupported verdict through is enforced here rather than left to callers.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Id = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=128)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _safe_relative(path: str) -> str:
    """Paths come from untrusted repositories, so they must stay inside their root."""
    parsed = PurePosixPath(path)
    if not path or "\\" in path or ":" in path or parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError(f"not a safe relative POSIX path: {path!r}")
    return path


RelPath = Annotated[str, AfterValidator(_safe_relative)]


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class StoredRecord(Record):
    """A record with an id, which can be put in the ledger and cited as evidence."""

    id: Id


class Unit(StrEnum):
    PERCENT = "percent"
    FRACTION = "fraction"
    RAW = "raw"


def _check_unit(value: float | None, unit: Unit) -> None:
    if unit is Unit.FRACTION and value is not None and abs(value) > 1:
        raise ValueError(f"{value} is not a fraction; use percent or raw")


class SourceLocation(Record):
    page: int | None = Field(default=None, ge=1)
    table: Text | None = None
    section: Text | None = None

    @model_validator(mode="after")
    def _has_location(self):
        if self.page is None and self.table is None and self.section is None:
            raise ValueError("a source location needs a page, table or section")
        return self


class AuditInfo(StoredRecord):
    title: Text
    # No default: sample data must never be presented as a real audit by omission.
    synthetic: bool


class Claim(StoredRecord):
    quote: Text
    source: SourceLocation
    metric: Text
    value: float
    unit: Unit
    dataset: Text
    model: Text
    confirmed_by_user: bool = False

    @model_validator(mode="after")
    def _unit_ok(self):
        _check_unit(self.value, self.unit)
        return self


class SettingStatus(StrEnum):
    STATED = "stated"
    INFERRED = "inferred"
    MISSING = "missing"


class Setting(Record):
    name: Text
    status: SettingStatus
    value: Text | None = None
    source: SourceLocation | None = None
    rationale: Text | None = None
    # A material setting must be shown to match before a claim can be Verified.
    material: bool

    @model_validator(mode="after")
    def _status_consistent(self):
        if self.status is SettingStatus.STATED and (self.value is None or self.source is None):
            raise ValueError("a stated setting needs a value and a source location")
        if self.status is SettingStatus.INFERRED and (self.value is None or self.rationale is None):
            raise ValueError("an inferred setting needs a value and a rationale")
        if self.status is SettingStatus.MISSING and self.value is not None:
            raise ValueError("a missing setting cannot have a value")
        return self


class Direction(StrEnum):
    TWO_SIDED = "two_sided"
    AT_LEAST = "at_least"
    AT_MOST = "at_most"


class Criterion(Record):
    metric: Text
    expected: float
    unit: Unit
    tolerance: float = Field(ge=0, description="Absolute, in the criterion's unit.")
    direction: Direction = Direction.TWO_SIDED

    @model_validator(mode="after")
    def _unit_ok(self):
        _check_unit(self.expected, self.unit)
        return self


class ArtifactKind(StrEnum):
    CODE = "code"
    DATA = "data"
    SPLIT = "split"
    WEIGHTS = "weights"
    ENVIRONMENT = "environment"


class ExperimentSpec(StoredRecord):
    claim_id: Id
    settings: tuple[Setting, ...]
    criteria: tuple[Criterion, ...] = Field(min_length=1)
    essential_artifacts: tuple[ArtifactKind, ...] = Field(min_length=1)
    frozen_at: AwareDatetime | None = None
    content_hash: Sha256 | None = None

    @model_validator(mode="after")
    def _consistent(self):
        if (self.frozen_at is None) != (self.content_hash is None):
            raise ValueError("frozen_at and content_hash are set together")
        names = [s.name for s in self.settings]
        if len(set(names)) != len(names):
            raise ValueError("setting names must be unique")
        # Otherwise a matching number could be Verified with no method check at all.
        if not any(s.material for s in self.settings):
            raise ValueError("a spec needs at least one material setting")
        metrics = [c.metric for c in self.criteria]
        if len(set(metrics)) != len(metrics):
            raise ValueError("one criterion per metric")
        return self


class Availability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    RESTRICTED = "restricted"


class ArtifactRecord(StoredRecord):
    claim_id: Id
    kind: ArtifactKind
    location: Text
    availability: Availability
    commit: Text | None = None
    sha256: Sha256 | None = None

    @model_validator(mode="after")
    def _identified(self):
        if self.availability is Availability.AVAILABLE and not (self.commit or self.sha256):
            raise ValueError("an available artifact needs a commit or a sha256")
        return self


class FindingResult(StrEnum):
    MATCH = "match"
    PARTIAL = "partial"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class FindingStage(StrEnum):
    IMPLEMENTATION = "implementation"  # audit question 1: code against the paper
    EXECUTION = "execution"  # audit question 2: the run against the intended configuration


class ConsistencyFinding(StoredRecord):
    claim_id: Id
    stage: FindingStage
    setting: Text
    result: FindingResult
    location: Text
    run_id: Id | None = None
    note: Text | None = None

    @model_validator(mode="after")
    def _run_for_execution(self):
        if (self.stage is FindingStage.EXECUTION) != (self.run_id is not None):
            raise ValueError("execution findings, and only those, name a run")
        return self


class Gate(StrEnum):
    CLAIMS = "gate1_claims"
    RUN = "gate2_run"


class Approval(StoredRecord):
    gate: Gate
    approved_hash: Sha256
    approved_at: AwareDatetime


class FileEvidence(Record):
    path: RelPath
    sha256: Sha256
    created_at: AwareDatetime | None = None


class RunLimits(Record):
    cpus: float = Field(gt=0)
    memory_mb: int = Field(gt=0)
    timeout_s: int = Field(gt=0)
    network_enabled: Literal[False] = False


class RunKind(StrEnum):
    ORIGINAL = "original"
    REPAIR = "repair"


class FailureCause(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    DEPENDENCY = "dependency"
    MISSING_ARTIFACT = "missing_artifact"
    RESOURCE_LIMIT = "resource_limit"
    TIMEOUT = "timeout"
    CODE_ERROR = "code_error"
    UNKNOWN = "unknown"


class RunRecord(StoredRecord):
    claim_id: Id
    spec_hash: Sha256
    kind: RunKind
    command: Text
    image_digest: Text
    limits: RunLimits
    started_at: AwareDatetime
    ended_at: AwareDatetime
    exit_code: int | None
    failure_cause: FailureCause | None = None
    log: FileEvidence
    input_files: tuple[FileEvidence, ...] = ()
    # None means reads were not recorded, which is different from "read nothing".
    files_read: tuple[RelPath, ...] | None = None
    outputs: tuple[FileEvidence, ...] = ()

    @property
    def completed(self) -> bool:
        return self.failure_cause is None

    @model_validator(mode="after")
    def _outcome_consistent(self):
        if self.ended_at < self.started_at:
            raise ValueError("a run cannot end before it starts")
        if self.completed and self.exit_code != 0:
            raise ValueError("a run without exit code 0 needs a failure cause")
        return self


class Capture(StrEnum):
    LOG = "log"
    OUTPUT_FILE = "output_file"


class MetricObservation(StoredRecord):
    run_id: Id
    metric: Text
    value: float | None  # None: the run reported the metric without a usable number
    unit: Unit
    capture: Capture
    source_path: RelPath
    source_sha256: Sha256

    @model_validator(mode="after")
    def _unit_ok(self):
        _check_unit(self.value, self.unit)
        return self


class CheckName(StrEnum):
    OUTPUT_CREATED_DURING_RUN = "output_created_during_run"
    VALUE_FOUND_IN_SOURCE = "value_found_in_source"
    VALUE_NOT_IN_INPUTS = "value_not_in_inputs"


class CheckResult(StrEnum):
    PASS = "pass"
    FLAGGED = "flagged"
    INCONCLUSIVE = "inconclusive"


class IntegrityCheck(StoredRecord):
    run_id: Id
    observation_id: Id
    name: CheckName
    result: CheckResult
    evidence: tuple[Text, ...] = Field(min_length=1)
    limitation: Text


class Status(StrEnum):
    VERIFIED = "Verified (Reproduced)"
    PARTIAL = "Partially reproduced"
    MISMATCH = "Result mismatch"
    NOT_VERIFIABLE = "Not verifiable"
    EXECUTION_FAILED = "Execution failed"


class ReasonCode(StrEnum):
    CLAIM_NOT_CONFIRMED = "claim_not_confirmed"
    SPEC_NOT_FROZEN = "spec_not_frozen"
    SPEC_INTEGRITY_FAILED = "spec_integrity_failed"
    CRITERIA_DO_NOT_MATCH_CLAIM = "criteria_do_not_match_claim"
    ESSENTIAL_ARTIFACT_MISSING = "essential_artifact_missing"
    NO_ORIGINAL_RUN = "no_original_run"
    MULTIPLE_ORIGINAL_RUNS = "multiple_original_runs"
    RUN_FAILED = "run_failed"
    RUN_SPEC_MISMATCH = "run_spec_mismatch"
    SPEC_FROZEN_AFTER_RUN = "spec_frozen_after_run"
    RUN_NOT_APPROVED = "run_not_approved"
    METRIC_NOT_OBSERVED = "metric_not_observed"
    CONFLICTING_OBSERVATIONS = "conflicting_observations"
    UNITS_NOT_COMPARABLE = "units_not_comparable"
    METRIC_NOT_SHOWN_COMPUTED = "metric_not_shown_computed"
    METHOD_MISMATCH = "method_mismatch"
    METHOD_NOT_CONFIRMED = "method_not_confirmed"
    OUTSIDE_CRITERIA = "outside_criteria"
    WITHIN_CRITERIA = "within_criteria"


class Comparison(Record):
    metric: Text
    expected: float
    observed: float | None
    unit: Unit
    tolerance: float
    outcome: Literal["within", "outside", "missing", "incomparable"]
    difference: float | None = None  # observed minus expected, in `unit`


class Verdict(StoredRecord):
    claim_id: Id
    status: Status
    reason_codes: tuple[ReasonCode, ...] = Field(min_length=1)
    evidence_ids: tuple[Id, ...] = Field(min_length=1)
    failure_cause: FailureCause | None = None
    comparisons: tuple[Comparison, ...] = ()
    possible_causes: tuple[Text, ...] = ()
    limitations: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def _cause_classified(self):
        if (self.status is Status.EXECUTION_FAILED) != (self.failure_cause is not None):
            raise ValueError("Execution failed, and only that status, carries a failure cause")
        return self
