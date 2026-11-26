import pytest
from conftest import make_claim, make_observation, make_run, make_spec
from pydantic import ValidationError

from reprotrace.schemas import (
    ArtifactRecord,
    ConsistencyFinding,
    FileEvidence,
    RunLimits,
    Setting,
    SourceLocation,
    Verdict,
)

VERDICT = dict(
    id="v", claim_id="c1", status="Not verifiable", reason_codes=["no_original_run"],
    evidence_ids=["c1"],
)


def test_claim_without_source_location_is_rejected():
    data = make_claim().model_dump()
    del data["source"]
    with pytest.raises(ValidationError):
        type(make_claim()).model_validate(data)
    with pytest.raises(ValidationError):
        SourceLocation()


def test_verdict_without_evidence_ids_is_rejected():
    Verdict.model_validate(VERDICT)
    with pytest.raises(ValidationError):
        Verdict.model_validate(VERDICT | {"evidence_ids": []})
    with pytest.raises(ValidationError):
        Verdict.model_validate({k: v for k, v in VERDICT.items() if k != "evidence_ids"})


@pytest.mark.parametrize(
    "setting",
    [
        dict(name="lr", value="0.1", source={"page": 1}, material=True),  # no status
        dict(name="lr", status="guessed", value="0.1", material=True),
        dict(name="lr", status="stated", value="0.1", material=True),  # no source
        dict(name="lr", status="stated", source={"page": 1}, material=True),  # no value
        dict(name="lr", status="inferred", value="0.1", material=True),  # no rationale
        dict(name="lr", status="missing", value="0.1", material=True),  # invented value
    ],
)
def test_setting_without_consistent_status_is_rejected(setting):
    with pytest.raises(ValidationError):
        Setting.model_validate(setting)


def test_spec_needs_a_material_setting_and_a_criterion():
    setting = dict(name="seed", status="missing", material=False)
    for change in ({"settings": [setting]}, {"settings": []}, {"criteria": []}):
        with pytest.raises(ValidationError):
            make_spec(**change)


def test_execution_failed_carries_a_cause_and_nothing_else_does():
    with pytest.raises(ValidationError):
        Verdict.model_validate(VERDICT | {"status": "Execution failed"})
    with pytest.raises(ValidationError):
        Verdict.model_validate(VERDICT | {"failure_cause": "timeout"})


def test_run_outcome_must_be_consistent():
    for change in ({"exit_code": 1}, {"exit_code": None}, {"ended_at": "2020-01-01T00:00:00Z"}):
        with pytest.raises(ValidationError):
            make_run(**change)
    with pytest.raises(ValidationError):
        make_run(started_at="2026-01-01T01:00:00")  # no timezone


def test_sandbox_limits_cannot_enable_network():
    with pytest.raises(ValidationError):
        RunLimits(cpus=1, memory_mb=1, timeout_s=1, network_enabled=True)


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "a/../../b", "C:/x", "a\\..\\b", ""])
def test_unsafe_paths_are_rejected(path):
    with pytest.raises(ValidationError):
        FileEvidence(path=path, sha256="a" * 64)


def test_values_must_be_finite_and_units_plausible():
    with pytest.raises(ValidationError):
        make_observation(value=float("nan"))
    with pytest.raises(ValidationError):
        make_claim(value=94.2, unit="fraction")


def test_available_artifact_needs_an_identifier():
    with pytest.raises(ValidationError):
        ArtifactRecord(id="a", claim_id="c1", kind="code", location="x", availability="available")


def test_execution_finding_names_its_run():
    base = dict(id="f", claim_id="c1", setting="s", result="match", location="x")
    with pytest.raises(ValidationError):
        ConsistencyFinding(**base, stage="execution")
    with pytest.raises(ValidationError):
        ConsistencyFinding(**base, stage="implementation", run_id="r1")


def test_records_are_immutable_and_reject_unknown_fields():
    with pytest.raises(ValidationError):
        make_claim().value = 1.0
    with pytest.raises(ValidationError):
        make_claim(surprise=1)
