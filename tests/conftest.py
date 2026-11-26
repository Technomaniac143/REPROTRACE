"""A consistent synthetic case that is Verified; tests change one thing at a time."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from reprotrace.evidence.hashing import record_hash
from reprotrace.schemas import *  # noqa: F403
from reprotrace.verification.freezing import freeze
from reprotrace.verification.verdict import CaseFile

T0 = datetime(2026, 1, 1, tzinfo=UTC)
START = T0 + timedelta(hours=1)
END = T0 + timedelta(hours=2)
SHA = "a" * 64
IN_SHA = "b" * 64


def make_claim(**changes) -> Claim:
    data = dict(
        id="c1", quote="94.2% accuracy", source=SourceLocation(page=1), metric="accuracy",
        value=94.2, unit="percent", dataset="X", model="CNN", confirmed_by_user=True,
    )
    return Claim.model_validate(data | changes)


def make_spec(**changes) -> ExperimentSpec:
    data = dict(
        id="s1", claim_id="c1",
        settings=[dict(name="split", status="stated", value="80/20", source={"page": 2},
                       material=True)],
        criteria=[dict(metric="accuracy", expected=94.2, unit="percent", tolerance=0.5)],
        essential_artifacts=["code", "data"],
    )
    return ExperimentSpec.model_validate(data | changes)


def make_run(**changes) -> RunRecord:
    data = dict(
        id="r1", claim_id="c1", spec_hash=SHA, kind="original", command="python train.py",
        image_digest="img", limits=dict(cpus=1, memory_mb=512, timeout_s=60), started_at=START,
        ended_at=END, exit_code=0, log=dict(path="run.log", sha256="c" * 64, created_at=END),
        input_files=[dict(path="train.py", sha256=IN_SHA)], files_read=["train.py"],
        outputs=[dict(path="metrics.json", sha256=SHA, created_at=END)],
    )
    return RunRecord.model_validate(data | changes)


def make_observation(**changes) -> MetricObservation:
    data = dict(
        id="o1", run_id="r1", metric="accuracy", value=94.0, unit="percent",
        capture="output_file", source_path="metrics.json", source_sha256=SHA,
    )
    return MetricObservation.model_validate(data | changes)


def make_checks(observation_id="o1", run_id="r1", **results) -> tuple[IntegrityCheck, ...]:
    return tuple(
        IntegrityCheck(
            id=f"k-{observation_id}-{n}", run_id=run_id, observation_id=observation_id, name=n,
            result=results.get(n.value, "pass"), evidence=("e",), limitation="l",
        )
        for n in CheckName
    )


def make_findings(implementation="match", execution="match", setting="split"):
    return tuple(
        ConsistencyFinding(
            id=f"f-{setting}-{stage}", claim_id="c1", stage=stage, setting=setting, result=result,
            location="train.py:1", run_id="r1" if stage == "execution" else None,
        )
        for stage, result in (("implementation", implementation), ("execution", execution))
    )


def make_artifact(kind="code", availability="available") -> ArtifactRecord:
    return ArtifactRecord(
        id=f"a-{kind}", claim_id="c1", kind=kind, location="x", availability=availability,
        sha256=SHA if availability == "available" else None,
    )


def make_case(*, claim=None, spec=None, run=None, observation=None, **parts) -> CaseFile:
    claim = claim or make_claim()
    spec = spec or make_spec()
    if spec.content_hash is None:
        spec = freeze(spec, claim, T0)
    run = run or make_run()
    run = run.model_copy(update={"spec_hash": spec.content_hash})
    case = CaseFile(
        claim=claim,
        spec=spec,
        artifacts=(make_artifact("code"), make_artifact("data")),
        findings=make_findings(),
        approvals=(
            Approval(id="g1", gate="gate1_claims", approved_hash=record_hash(claim),
                     approved_at=T0),
            Approval(id="g2", gate="gate2_run", approved_hash=spec.content_hash, approved_at=T0),
        ),
        runs=(run,),
        observations=(observation or make_observation(),),
        checks=make_checks(),
    )
    return replace(case, **parts)


@pytest.fixture
def case() -> CaseFile:
    return make_case()
