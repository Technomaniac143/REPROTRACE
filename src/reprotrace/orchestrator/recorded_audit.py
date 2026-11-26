"""Audit recorded evidence: bundle -> ledger -> integrity checks -> verdicts -> report.

Nothing is executed here. Integrity checks and verdicts are always computed, never read from
the bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import model_validator

from ..evidence.ledger import Ledger
from ..report.markdown import render_report
from ..schemas import (
    Approval,
    ArtifactRecord,
    AuditInfo,
    Claim,
    ConsistencyFinding,
    ExperimentSpec,
    IntegrityCheck,
    MetricObservation,
    Record,
    RunRecord,
    Verdict,
)
from ..ui.dashboard import render_dashboard
from ..verification.integrity import run_checks
from ..verification.verdict import CaseFile, decide


class AuditError(Exception):
    pass


class AuditBundle(Record):
    audit: AuditInfo
    claims: tuple[Claim, ...]
    specs: tuple[ExperimentSpec, ...]
    artifacts: tuple[ArtifactRecord, ...] = ()
    findings: tuple[ConsistencyFinding, ...] = ()
    approvals: tuple[Approval, ...] = ()
    runs: tuple[RunRecord, ...] = ()
    observations: tuple[MetricObservation, ...] = ()

    @model_validator(mode="after")
    def _references_resolve(self):
        claims = {c.id for c in self.claims}
        runs = {r.id: r for r in self.runs}
        settings = {(s.claim_id, setting.name) for s in self.specs for setting in s.settings}
        if sorted(s.claim_id for s in self.specs) != sorted(claims):
            raise ValueError("each claim needs exactly one spec")
        for record in (*self.artifacts, *self.findings, *self.runs):
            if record.claim_id not in claims:
                raise ValueError(f"{record.id}: unknown claim {record.claim_id}")
        for finding in self.findings:
            if (finding.claim_id, finding.setting) not in settings:
                raise ValueError(f"{finding.id}: setting {finding.setting!r} is not in the spec")
            if finding.run_id is not None and (
                finding.run_id not in runs or runs[finding.run_id].claim_id != finding.claim_id
            ):
                raise ValueError(f"{finding.id}: not a run of claim {finding.claim_id}")
        for observation in self.observations:
            if observation.run_id not in runs:
                raise ValueError(f"{observation.id}: unknown run {observation.run_id}")
        # Run ids name directories, and ':' is not allowed in a Windows file name.
        if bad := [r for r in runs if ":" in r]:
            raise ValueError(f"run ids cannot contain ':': {bad}")
        return self


@dataclass(frozen=True)
class AuditResult:
    verdicts: tuple[Verdict, ...]
    report_path: Path
    dashboard_path: Path


def run_recorded_audit(bundle_dir: Path, out: Path) -> AuditResult:
    bundle_file = bundle_dir / "bundle.json"
    bundle = AuditBundle.model_validate_json(bundle_file.read_text(encoding="utf-8"))
    if out.exists() and any(out.iterdir()):
        raise AuditError(f"{out} is not empty; evidence is never overwritten")

    with Ledger(out) as ledger:
        for record in (
            bundle.audit,
            *bundle.claims,
            *bundle.specs,
            *bundle.artifacts,
            *bundle.findings,
            *bundle.approvals,
            *bundle.runs,
            *bundle.observations,
        ):
            ledger.add(record)
        for run in bundle.runs:
            for file in (run.log, *run.outputs):
                ledger.add_file(_outputs(bundle_dir, run) / file.path, file.sha256)

        verdicts = []
        for claim in bundle.claims:
            case = _case_file(bundle, claim, bundle_dir)
            for check in case.checks:
                ledger.add(check)
            verdict = decide(case)
            ledger.add(verdict)
            verdicts.append(verdict)

        if problems := ledger.verify():
            raise AuditError("ledger failed verification: " + "; ".join(problems))
        report_path = out / "report.md"
        report_path.write_text(render_report(ledger), encoding="utf-8", newline="\n")
        dashboard_path = out / "dashboard.html"
        dashboard_path.write_text(render_dashboard(ledger), encoding="utf-8", newline="\n")
    return AuditResult(tuple(verdicts), report_path, dashboard_path)


def _case_file(bundle: AuditBundle, claim: Claim, bundle_dir: Path) -> CaseFile:
    spec = next(s for s in bundle.specs if s.claim_id == claim.id)
    runs = tuple(r for r in bundle.runs if r.claim_id == claim.id)
    by_id = {r.id: r for r in runs}
    observations = tuple(o for o in bundle.observations if o.run_id in by_id)
    criteria = {c.metric: c for c in spec.criteria}

    checks: list[IntegrityCheck] = []
    for observation in observations:
        if criterion := criteria.get(observation.metric):
            run = by_id[observation.run_id]
            checks.extend(
                run_checks(
                    run,
                    criterion,
                    observation,
                    inputs_root=bundle_dir / "files" / run.id / "inputs",
                    source_file=_outputs(bundle_dir, run) / observation.source_path,
                )
            )
    return CaseFile(
        claim=claim,
        spec=spec,
        artifacts=tuple(a for a in bundle.artifacts if a.claim_id == claim.id),
        findings=tuple(f for f in bundle.findings if f.claim_id == claim.id),
        approvals=bundle.approvals,
        runs=runs,
        observations=observations,
        checks=tuple(checks),
    )


def _outputs(bundle_dir: Path, run: RunRecord) -> Path:
    return bundle_dir / "files" / run.id / "outputs"
