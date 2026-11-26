from datetime import timedelta

import pytest
from conftest import T0, make_claim, make_spec

from reprotrace.schemas import ArtifactKind, Criterion, ExperimentSpec
from reprotrace.verification.freezing import freeze, is_intact


def test_frozen_spec_is_intact_and_survives_a_round_trip():
    spec = freeze(make_spec(), make_claim(), T0)
    assert is_intact(spec)
    assert is_intact(ExperimentSpec.model_validate_json(spec.model_dump_json()))


@pytest.mark.parametrize(
    "change",
    [
        {"criteria": (Criterion(metric="accuracy", expected=94.2, unit="percent", tolerance=5),)},
        {"essential_artifacts": (ArtifactKind.CODE,)},
        {"frozen_at": T0 - timedelta(days=1)},
        {"settings": ()},
    ],
)
def test_changing_a_frozen_spec_fails_the_hash_check(change):
    spec = freeze(make_spec(), make_claim(), T0)
    assert not is_intact(spec.model_copy(update=change))


def test_unfrozen_spec_is_not_intact_and_frozen_spec_cannot_be_refrozen():
    assert not is_intact(make_spec())
    with pytest.raises(ValueError, match="already frozen"):
        freeze(freeze(make_spec(), make_claim(), T0), make_claim(), T0)


def test_criteria_must_include_the_claimed_number():
    with pytest.raises(ValueError, match="no criterion"):
        freeze(make_spec(), make_claim(value=95.0), T0)
