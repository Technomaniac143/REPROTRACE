"""Regenerate fixtures/synthetic. Every record and file it writes is invented.

Run: uv run python fixtures/build_synthetic.py
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from reprotrace.evidence.hashing import record_hash, sha256_bytes
from reprotrace.orchestrator.recorded_audit import AuditBundle
from reprotrace.schemas import *  # noqa: F403
from reprotrace.verification.freezing import freeze

ROOT = Path(__file__).parent / "synthetic"
T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
FROZEN = T0 + timedelta(minutes=10)
APPROVED = T0 + timedelta(minutes=20)
START = T0 + timedelta(minutes=30)
END = T0 + timedelta(minutes=40)

PAGE = SourceLocation(page=6, table="2")
TRAIN_PY = "import data\n\nmodel = fit(data.train)\nsave(evaluate(model, data.test))\n"


class Builder:
    def __init__(self) -> None:
        self.parts: dict[str, list] = {
            k: []
            for k in (
                "claims specs artifacts findings approvals runs observations".split()
            )
        }

    def case(
        self,
        name: str,
        claimed: float,
        observed: float | None,
        *,
        second: tuple[float, float] | None = None,  # claimed and observed macro F1
        missing: tuple[ArtifactKind, ...] = (),
        essential: tuple[ArtifactKind, ...] = (ArtifactKind.CODE, ArtifactKind.DATA),
        seed_stated: bool = True,
        findings: dict[str, FindingResult] | None = None,
        failure: FailureCause | None = None,
        extra_inputs: dict[str, str] | None = None,
        extra_reads: tuple[str, ...] = (),
    ) -> None:
        metrics = [("accuracy", claimed, observed)]
        if second:
            metrics.append(("macro_f1", *second))

        claim = Claim(
            id=f"claim-{name}",
            quote=f"Our proposed CNN achieves {claimed}% accuracy on Dataset X.",
            source=PAGE,
            metric="accuracy",
            value=claimed,
            unit=Unit.PERCENT,
            dataset="Dataset X (synthetic)",
            model="Example CNN (synthetic)",
            confirmed_by_user=True,
        )
        stated = {"status": SettingStatus.STATED, "source": SourceLocation(section="4.1")}
        spec = freeze(
            ExperimentSpec(
                id=f"spec-{name}",
                claim_id=claim.id,
                settings=(
                    Setting(name="data split", value="80/20 held-out", material=True, **stated),
                    Setting(name="preprocessing", value="standardise", material=True, **stated),
                    Setting(name="training seed", value="7", material=False, **stated)
                    if seed_stated
                    else Setting(
                        name="training seed", status=SettingStatus.MISSING, material=False
                    ),
                ),
                criteria=tuple(
                    Criterion(metric=m, expected=e, unit=Unit.PERCENT, tolerance=0.5)
                    for m, e, _ in metrics
                ),
                essential_artifacts=essential,
            ),
            claim,
            FROZEN,
        )
        self.parts["claims"].append(claim)
        self.parts["specs"].append(spec)
        self.parts["approvals"].append(
            Approval(
                id=f"gate1-{name}",
                gate=Gate.CLAIMS,
                approved_hash=record_hash(claim),
                approved_at=T0,
            )
        )
        for kind in (ArtifactKind.CODE, ArtifactKind.DATA, ArtifactKind.WEIGHTS):
            present = kind not in missing
            self.parts["artifacts"].append(
                ArtifactRecord(
                    id=f"artifact-{name}-{kind}",
                    claim_id=claim.id,
                    kind=kind,
                    location=f"synthetic://{name}/{kind}",
                    availability=Availability.AVAILABLE if present else Availability.MISSING,
                    sha256=sha256_bytes(f"{name}/{kind}".encode()) if present else None,
                )
            )

        will_run = not set(missing) & set(essential)
        run_id = f"run-{name}"
        for setting in ("data split", "preprocessing"):
            result = (findings or {}).get(setting, FindingResult.MATCH)
            slug = setting.replace(" ", "-")
            self.parts["findings"].append(
                ConsistencyFinding(
                    id=f"finding-{name}-code-{slug}",
                    claim_id=claim.id,
                    stage=FindingStage.IMPLEMENTATION,
                    setting=setting,
                    result=result,
                    location="train.py:3",
                )
            )
            if will_run and failure is None:
                self.parts["findings"].append(
                    ConsistencyFinding(
                        id=f"finding-{name}-run-{slug}",
                        claim_id=claim.id,
                        stage=FindingStage.EXECUTION,
                        setting=setting,
                        result=result,
                        location="run.log",
                        run_id=run_id,
                    )
                )
        if not will_run:
            return

        self.parts["approvals"].append(
            Approval(
                id=f"gate2-{name}",
                gate=Gate.RUN,
                approved_hash=spec.content_hash,
                approved_at=APPROVED,
            )
        )
        base = ROOT / "files" / run_id
        inputs = {"train.py": TRAIN_PY, **(extra_inputs or {})}
        input_files = tuple(self.write(base / "inputs", p, t, None) for p, t in inputs.items())
        outputs = ()
        if failure is None:
            log_text = "synthetic run finished\n"
            metrics_file = self.write(
                base / "outputs",
                "metrics.json",
                json.dumps({m: o for m, _, o in metrics}) + "\n",
                END - timedelta(minutes=1),
            )
            outputs = (metrics_file,)
            for metric, _, value in metrics:
                self.parts["observations"].append(
                    MetricObservation(
                        id=f"obs-{name}-{metric}",
                        run_id=run_id,
                        metric=metric,
                        value=value,
                        unit=Unit.PERCENT,
                        capture=Capture.OUTPUT_FILE,
                        source_path=metrics_file.path,
                        source_sha256=metrics_file.sha256,
                    )
                )
        else:
            log_text = "synthetic run failed while installing dependencies\n"
        self.parts["runs"].append(
            RunRecord(
                id=run_id,
                claim_id=claim.id,
                spec_hash=spec.content_hash,
                kind=RunKind.ORIGINAL,
                command="python train.py",
                image_digest="synthetic-image",
                limits=RunLimits(cpus=2, memory_mb=2048, timeout_s=900),
                started_at=START,
                ended_at=END,
                exit_code=0 if failure is None else 1,
                failure_cause=failure,
                log=self.write(base / "outputs", "run.log", log_text, END),
                input_files=input_files,
                files_read=("train.py", *extra_reads),
                outputs=outputs,
            )
        )

    @staticmethod
    def write(root: Path, path: str, text: str, created: datetime | None) -> FileEvidence:
        root.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        (root / path).write_bytes(data)
        return FileEvidence(path=path, sha256=sha256_bytes(data), created_at=created)


def build() -> None:
    shutil.rmtree(ROOT / "files", ignore_errors=True)
    b = Builder()
    b.case("verified", 91.37, 91.52)
    # The worked example in master section 6.1.
    b.case(
        "mismatch",
        94.2,
        92.1,
        missing=(ArtifactKind.WEIGHTS,),
        seed_stated=False,
        findings={"preprocessing": FindingResult.UNKNOWN},
    )
    b.case("partial", 89.64, 89.71, second=(88.15, 84.02))
    b.case("wrong-method", 93.18, 93.18, findings={"data split": FindingResult.MISMATCH})
    # The README mentions the claim but was not read; the saved results file was.
    b.case(
        "copied",
        95.43,
        95.43,
        extra_inputs={
            "README.md": "We report 95.43% accuracy.\n",
            "saved_results.json": '{"accuracy": 95.43}\n',
        },
        extra_reads=("saved_results.json",),
    )
    b.case("missing-data", 90.26, None, missing=(ArtifactKind.DATA,))
    b.case("failed", 92.83, None, failure=FailureCause.DEPENDENCY)

    bundle = AuditBundle(
        audit=AuditInfo(id="audit-synthetic", title="Synthetic example", synthetic=True),
        **{k: tuple(v) for k, v in b.parts.items()},
    )
    (ROOT / "bundle.json").write_text(
        bundle.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    build()
