"""Verdict engine: the decision order in Project.md section 6, first match wins.

It reads records only. It never sees an agent's summary, and no LLM is involved.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..evidence.hashing import record_hash
from ..schemas import (
    Approval,
    ArtifactRecord,
    Availability,
    CheckResult,
    Claim,
    Comparison,
    ConsistencyFinding,
    ExperimentSpec,
    FailureCause,
    FindingResult,
    FindingStage,
    Gate,
    IntegrityCheck,
    MetricObservation,
    ReasonCode,
    RunKind,
    RunRecord,
    Setting,
    SettingStatus,
    Status,
    Verdict,
)
from .comparison import compare
from .freezing import criteria_match_claim, is_intact
from .integrity import REQUIRED_CHECKS, recorded_source


@dataclass(frozen=True)
class CaseFile:
    """Everything recorded about one claim."""

    claim: Claim
    spec: ExperimentSpec
    artifacts: tuple[ArtifactRecord, ...] = ()
    findings: tuple[ConsistencyFinding, ...] = ()
    approvals: tuple[Approval, ...] = ()
    runs: tuple[RunRecord, ...] = ()
    observations: tuple[MetricObservation, ...] = ()
    checks: tuple[IntegrityCheck, ...] = ()

    def __post_init__(self) -> None:
        owners = (
            self.spec.claim_id,
            *(r.claim_id for r in (*self.artifacts, *self.findings, *self.runs)),
        )
        if any(owner != self.claim.id for owner in owners):
            raise ValueError(f"records from another claim in the case file for {self.claim.id}")


def decide(case: CaseFile) -> Verdict:
    return _Decision(case).decide()


class _Decision:
    def __init__(self, case: CaseFile) -> None:
        self.case = case
        self.evidence: list[str] = [case.claim.id, case.spec.id]
        self.limitations: list[str] = []
        self.comparisons: tuple[Comparison, ...] = ()

    def decide(self) -> Verdict:
        self._note_general_limitations()
        case, spec = self.case, self.case.spec

        # 0. Without a confirmed claim and an intact frozen spec, nothing below means anything.
        if reasons := self._protocol_problems():
            return self._verdict(Status.NOT_VERIFIABLE, reasons)

        # 1. Essential artifacts.
        self._cite(*case.artifacts)
        available = {a.kind for a in case.artifacts if a.availability is Availability.AVAILABLE}
        if absent := [k for k in spec.essential_artifacts if k not in available]:
            self.limitations.append(f"Essential artifacts unavailable: {', '.join(absent)}.")
            return self._verdict(
                Status.NOT_VERIFIABLE, [ReasonCode.ESSENTIAL_ARTIFACT_MISSING]
            )

        # 2. Did the original run complete? Repair runs never decide a verdict (hard rule 5).
        originals = [r for r in case.runs if r.kind is RunKind.ORIGINAL]
        self._cite(*originals)
        completed = [r for r in originals if r.completed]
        if not originals:
            return self._verdict(Status.NOT_VERIFIABLE, [ReasonCode.NO_ORIGINAL_RUN])
        if not completed:
            last = max(originals, key=lambda r: r.started_at)
            return self._verdict(
                Status.EXECUTION_FAILED, [ReasonCode.RUN_FAILED], cause=last.failure_cause
            )
        if len(completed) > 1:
            # Choosing one would be choosing the result (T6: one run).
            return self._verdict(Status.NOT_VERIFIABLE, [ReasonCode.MULTIPLE_ORIGINAL_RUNS])
        run = completed[0]
        if failed := len(originals) - 1:
            self.limitations.append(f"{failed} earlier original run(s) did not complete.")

        # 3. Is the evidence complete, and was the metric shown to be computed in this run?
        findings = self._relevant_findings(run)
        self._cite(*findings)
        if reasons := self._evidence_problems(run):
            return self._verdict(Status.NOT_VERIFIABLE, reasons)

        # 4. A different method makes the number irrelevant, even when it matches.
        material = [s for s in spec.settings if s.material]
        mismatched = {f.setting for f in findings if f.result is FindingResult.MISMATCH}
        if differing := [s.name for s in material if s.name in mismatched]:
            self.limitations.append(f"Method or configuration differs: {', '.join(differing)}.")
            return self._verdict(Status.NOT_VERIFIABLE, [ReasonCode.METHOD_MISMATCH])

        # 5. Compare with the criteria.
        within = [c for c in self.comparisons if c.outcome == "within"]
        if not within:
            return self._verdict(Status.MISMATCH, [ReasonCode.OUTSIDE_CRITERIA])

        # 6. Verified needs matching conditions to be shown, not merely not contradicted.
        if unconfirmed := [s.name for s in material if not self._confirmed(s, findings)]:
            self.limitations.append(f"Not confirmed to match: {', '.join(unconfirmed)}.")
            return self._verdict(Status.NOT_VERIFIABLE, [ReasonCode.METHOD_NOT_CONFIRMED])
        if len(within) < len(self.comparisons):
            return self._verdict(
                Status.PARTIAL, [ReasonCode.WITHIN_CRITERIA, ReasonCode.OUTSIDE_CRITERIA]
            )
        return self._verdict(Status.VERIFIED, [ReasonCode.WITHIN_CRITERIA])

    def _protocol_problems(self) -> list[ReasonCode]:
        claim, spec = self.case.claim, self.case.spec
        reasons = []
        gate1 = self._approval(Gate.CLAIMS, record_hash(claim))
        if not claim.confirmed_by_user or gate1 is None:
            reasons.append(ReasonCode.CLAIM_NOT_CONFIRMED)
        else:
            self._cite(gate1)
        if spec.content_hash is None:
            reasons.append(ReasonCode.SPEC_NOT_FROZEN)
        elif not is_intact(spec):
            reasons.append(ReasonCode.SPEC_INTEGRITY_FAILED)
        if not criteria_match_claim(spec, claim):
            reasons.append(ReasonCode.CRITERIA_DO_NOT_MATCH_CLAIM)
        return reasons

    def _evidence_problems(self, run: RunRecord) -> list[ReasonCode]:
        spec = self.case.spec
        reasons: list[ReasonCode] = []
        if run.spec_hash != spec.content_hash:
            reasons.append(ReasonCode.RUN_SPEC_MISMATCH)
        if spec.frozen_at > run.started_at:
            reasons.append(ReasonCode.SPEC_FROZEN_AFTER_RUN)
        gate2 = self._approval(Gate.RUN, run.spec_hash)
        if gate2 is None or gate2.approved_at > run.started_at:
            reasons.append(ReasonCode.RUN_NOT_APPROVED)
        else:
            self._cite(gate2)

        comparisons = []
        for criterion in spec.criteria:
            observations = [
                o
                for o in self.case.observations
                if o.run_id == run.id and o.metric == criterion.metric
            ]
            self._cite(*observations)
            results = [compare(criterion, o.value, o.unit) for o in observations]
            usable = [c for c in results if c.outcome in ("within", "outside")]
            if any(c.outcome == "incomparable" for c in results):
                reasons.append(ReasonCode.UNITS_NOT_COMPARABLE)
            elif not usable:
                reasons.append(ReasonCode.METRIC_NOT_OBSERVED)
            elif len(usable) < len(results) or len({c.observed for c in usable}) > 1:
                reasons.append(ReasonCode.CONFLICTING_OBSERVATIONS)
            else:
                comparisons.append(usable[0])
                if not all(self._shown_computed(run, o) for o in observations):
                    reasons.append(ReasonCode.METRIC_NOT_SHOWN_COMPUTED)
        self.comparisons = tuple(comparisons)
        return list(dict.fromkeys(reasons))

    def _shown_computed(self, run: RunRecord, observation: MetricObservation) -> bool:
        checks = [
            c
            for c in self.case.checks
            if c.run_id == run.id and c.observation_id == observation.id
        ]
        self._cite(*checks)
        return (
            recorded_source(run, observation) is not None
            and {c.name for c in checks} >= REQUIRED_CHECKS
            and all(c.result is CheckResult.PASS for c in checks)
        )

    def _relevant_findings(self, run: RunRecord) -> list[ConsistencyFinding]:
        return [
            f
            for f in self.case.findings
            if f.stage is FindingStage.IMPLEMENTATION or f.run_id == run.id
        ]

    @staticmethod
    def _confirmed(setting: Setting, findings: list[ConsistencyFinding]) -> bool:
        if setting.status is SettingStatus.MISSING:
            return False
        for stage in FindingStage:
            results = [f.result for f in findings if f.setting == setting.name and f.stage is stage]
            if not results or any(r is not FindingResult.MATCH for r in results):
                return False
        return True

    def _approval(self, gate: Gate, approved_hash: str) -> Approval | None:
        matching = [
            a
            for a in self.case.approvals
            if a.gate is gate and a.approved_hash == approved_hash
        ]
        return min(matching, key=lambda a: a.approved_at, default=None)

    def _note_general_limitations(self) -> None:
        for setting in self.case.spec.settings:
            if setting.status is SettingStatus.MISSING:
                self.limitations.append(f"The paper does not specify {setting.name}.")
            elif setting.status is SettingStatus.INFERRED:
                self.limitations.append(f"{setting.name} was inferred, not stated in the paper.")
        self.limitations.append(
            "One run against a fixed tolerance; run-to-run variation was not measured."
        )

    def _possible_causes(self) -> list[str]:
        """Listed from recorded gaps only. Nothing here is a diagnosis."""
        causes = [
            f"{a.kind} not available" for a in self.case.artifacts
            if a.availability is not Availability.AVAILABLE
        ]
        causes += [
            f"{s.name} not specified in the paper" for s in self.case.spec.settings
            if s.status is SettingStatus.MISSING
        ]
        causes += [
            f"{f.setting} {'differs' if f.result is FindingResult.MISMATCH else 'needs confirmation'}"
            for f in self.case.findings if f.result is not FindingResult.MATCH
        ]
        causes.append("normal variation between runs")
        return list(dict.fromkeys(causes))

    def _cite(self, *records) -> None:
        self.evidence.extend(r.id for r in records)

    def _verdict(
        self,
        status: Status,
        reasons: list[ReasonCode],
        cause: FailureCause | None = None,
    ) -> Verdict:
        differs = status in (Status.MISMATCH, Status.PARTIAL)
        return Verdict(
            id=f"verdict:{self.case.claim.id}",
            claim_id=self.case.claim.id,
            status=status,
            reason_codes=tuple(reasons),
            evidence_ids=tuple(dict.fromkeys(self.evidence)),
            failure_cause=cause,
            comparisons=self.comparisons,
            possible_causes=tuple(self._possible_causes()) if differs else (),
            limitations=tuple(self.limitations),
        )
