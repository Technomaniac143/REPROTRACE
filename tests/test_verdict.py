from dataclasses import replace
from datetime import timedelta

import pytest
from conftest import (
    START,
    T0,
    make_artifact,
    make_case,
    make_checks,
    make_claim,
    make_findings,
    make_observation,
    make_run,
    make_spec,
)

from reprotrace.schemas import ReasonCode, Status
from reprotrace.verification.freezing import freeze
from reprotrace.verification.verdict import decide

FAILED = dict(exit_code=1, failure_cause="dependency")


def outcome(case):
    verdict = decide(case)
    return verdict.status, verdict.reason_codes


def not_verifiable(reason):
    return Status.NOT_VERIFIABLE, (ReasonCode(reason),)


TWO_CRITERIA = [
    dict(metric="accuracy", expected=94.2, unit="percent", tolerance=0.5),
    dict(metric="f1", expected=90.0, unit="percent", tolerance=0.5),
]


def two_metric_case(accuracy, f1):
    return make_case(
        spec=make_spec(criteria=TWO_CRITERIA),
        observations=(
            make_observation(value=accuracy),
            make_observation(id="o2", metric="f1", value=f1),
        ),
        checks=make_checks("o1") + make_checks("o2"),
    )


# One test per status


def test_verified(case):
    assert outcome(case) == (Status.VERIFIED, (ReasonCode.WITHIN_CRITERIA,))


def test_result_mismatch():
    verdict = decide(make_case(observation=make_observation(value=92.1)))
    assert verdict.status is Status.MISMATCH
    assert verdict.possible_causes
    assert verdict.comparisons[0].difference == -2.1


def test_partially_reproduced_only_with_several_criteria():
    assert decide(two_metric_case(94.0, 80.0)).status is Status.PARTIAL
    assert decide(two_metric_case(94.0, 90.0)).status is Status.VERIFIED
    assert decide(two_metric_case(80.0, 80.0)).status is Status.MISMATCH


def test_execution_failed_is_classified():
    verdict = decide(make_case(run=make_run(**FAILED)))
    assert verdict.status is Status.EXECUTION_FAILED
    assert verdict.failure_cause == "dependency"


def test_not_verifiable_when_an_essential_artifact_is_missing(case):
    case = replace(case, artifacts=(make_artifact("code"), make_artifact("data", "missing")))
    assert outcome(case) == not_verifiable("essential_artifact_missing")


# Decision order


def test_unrecorded_essential_artifact_counts_as_missing(case):
    assert outcome(replace(case, artifacts=(make_artifact("code"),))) == not_verifiable(
        "essential_artifact_missing"
    )


def test_missing_artifact_comes_before_failed_run():
    case = make_case(run=make_run(**FAILED), artifacts=())
    assert outcome(case) == not_verifiable("essential_artifact_missing")


def test_incomplete_evidence_comes_before_result_mismatch():
    case = make_case(
        observation=make_observation(value=92.1),
        checks=make_checks(value_not_in_inputs="flagged"),
    )
    assert outcome(case) == not_verifiable("metric_not_shown_computed")


# A matching metric from the wrong method is never Verified


@pytest.mark.parametrize("findings", [
    make_findings(implementation="mismatch"),
    make_findings(execution="mismatch"),
])
def test_wrong_method_with_matching_metric(case, findings):
    assert outcome(replace(case, findings=findings)) == not_verifiable("method_mismatch")


@pytest.mark.parametrize("findings", [
    (),
    make_findings()[:1],
    make_findings()[1:],
    make_findings(implementation="unknown"),
    make_findings(execution="partial"),
])
def test_unconfirmed_method_with_matching_metric(case, findings):
    assert outcome(replace(case, findings=findings)) == not_verifiable("method_not_confirmed")


def test_unspecified_material_setting_cannot_be_confirmed():
    spec = make_spec(settings=[dict(name="split", status="missing", material=True)])
    assert outcome(make_case(spec=spec)) == not_verifiable("method_not_confirmed")


def test_unconfirmed_method_does_not_hide_a_result_mismatch():
    # Master section 6.1: partly matched settings, 92.1 against 94.2, is a Result mismatch.
    case = make_case(
        observation=make_observation(value=92.1), findings=make_findings(implementation="unknown")
    )
    verdict = decide(case)
    assert verdict.status is Status.MISMATCH
    assert "split needs confirmation" in verdict.possible_causes


def test_immaterial_difference_does_not_block():
    settings = [s.model_dump() for s in make_spec().settings]
    settings.append(dict(name="seed", status="missing", material=False))
    case = make_case(spec=make_spec(settings=settings))
    case = replace(
        case, findings=case.findings + make_findings("mismatch", "mismatch", setting="seed")
    )
    verdict = decide(case)
    assert verdict.status is Status.VERIFIED
    assert "The paper does not specify seed." in verdict.limitations


# Protocol


def test_unconfirmed_claim(case):
    expected = not_verifiable("claim_not_confirmed")
    assert outcome(make_case(claim=make_claim(confirmed_by_user=False))) == expected
    assert outcome(replace(case, approvals=case.approvals[1:])) == expected


def test_claim_edited_after_confirmation(case):
    edited = case.claim.model_copy(update={"quote": "something else"})
    assert outcome(replace(case, claim=edited)) == not_verifiable("claim_not_confirmed")


def test_spec_problems(case):
    assert outcome(replace(case, spec=make_spec())) == not_verifiable("spec_not_frozen")
    loosened = case.spec.criteria[0].model_copy(update={"tolerance": 50})
    tampered = case.spec.model_copy(update={"criteria": (loosened,)})
    assert outcome(replace(case, spec=tampered)) == not_verifiable("spec_integrity_failed")


def test_spec_refrozen_after_the_run_is_caught(case):
    loose = [dict(metric="accuracy", expected=94.2, unit="percent", tolerance=50)]
    refrozen = freeze(make_spec(criteria=loose), case.claim, START + timedelta(hours=5))
    status, reasons = outcome(replace(case, spec=refrozen))
    assert status is Status.NOT_VERIFIABLE
    assert {ReasonCode.RUN_SPEC_MISMATCH, ReasonCode.SPEC_FROZEN_AFTER_RUN} <= set(reasons)


def test_backdated_refreeze_is_still_caught(case):
    loose = [dict(metric="accuracy", expected=94.2, unit="percent", tolerance=50)]
    refrozen = freeze(make_spec(criteria=loose), case.claim, T0)
    assert outcome(replace(case, spec=refrozen)) == not_verifiable("run_spec_mismatch")


def test_run_must_be_approved_before_it_starts(case):
    gate1, gate2 = case.approvals
    late = gate2.model_copy(update={"approved_at": START + timedelta(seconds=1)})
    for approvals in ((gate1,), (gate1, late)):
        assert outcome(replace(case, approvals=approvals)) == not_verifiable("run_not_approved")


# Runs


def test_no_run(case):
    assert outcome(replace(case, runs=())) == not_verifiable("no_original_run")


def test_repair_run_never_decides():
    assert outcome(make_case(run=make_run(kind="repair"))) == not_verifiable("no_original_run")


def test_several_completed_runs_are_not_chosen_between(case):
    again = case.runs[0].model_copy(update={"id": "r2"})
    assert outcome(replace(case, runs=(*case.runs, again))) == not_verifiable(
        "multiple_original_runs"
    )


def test_failed_attempt_before_a_completed_run_is_disclosed(case):
    failed = make_run(id="r0", **FAILED)
    verdict = decide(replace(case, runs=(failed, *case.runs)))
    assert verdict.status is Status.VERIFIED
    assert "r0" in verdict.evidence_ids
    assert any("did not complete" in text for text in verdict.limitations)


# Observations and integrity


@pytest.mark.parametrize(
    ("observations", "reason"),
    [
        ((), "metric_not_observed"),
        ((make_observation(value=None),), "metric_not_observed"),
        ((make_observation(unit="raw"),), "units_not_comparable"),
        ((make_observation(), make_observation(id="o2", value=90.0)), "conflicting_observations"),
        ((make_observation(), make_observation(id="o2", value=None)), "conflicting_observations"),
        ((make_observation(source_sha256="d" * 64),), "metric_not_shown_computed"),
    ],
)
def test_unusable_observations(case, observations, reason):
    assert outcome(replace(case, observations=observations)) == not_verifiable(reason)


@pytest.mark.parametrize("result", ["flagged", "inconclusive"])
@pytest.mark.parametrize(
    "check", ["output_created_during_run", "value_found_in_source", "value_not_in_inputs"]
)
def test_every_integrity_check_must_pass(case, check, result):
    case = replace(case, checks=make_checks(**{check: result}))
    assert outcome(case) == not_verifiable("metric_not_shown_computed")


def test_absent_or_borrowed_integrity_checks_do_not_count(case):
    expected = not_verifiable("metric_not_shown_computed")
    for checks in ((), case.checks[1:], make_checks("other"), make_checks(run_id="r9")):
        assert outcome(replace(case, checks=checks)) == expected


def test_verdict_cites_the_records_it_used(case):
    ids = set(decide(case).evidence_ids)
    used = (
        case.claim, case.spec, *case.artifacts, *case.findings, *case.approvals, *case.runs,
        *case.observations, *case.checks,
    )
    assert ids == {r.id for r in used}


def test_records_from_another_claim_are_rejected(case):
    with pytest.raises(ValueError, match="another claim"):
        replace(case, runs=(make_run(claim_id="c2"),))
