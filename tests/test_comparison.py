import pytest

from reprotrace.schemas import Criterion
from reprotrace.verification.comparison import compare


def criterion(**changes):
    data = dict(metric="accuracy", expected=94.2, unit="percent", tolerance=0.5)
    return Criterion.model_validate(data | changes)


@pytest.mark.parametrize(
    ("observed", "outcome"),
    [
        (94.0, "within"), (94.2, "within"), (92.1, "outside"), (96.0, "outside"),
        # Exactly on the boundary counts as within; just beyond does not.
        (93.7, "within"), (94.7, "within"), (93.69, "outside"), (94.71, "outside"),
    ],
)
def test_two_sided_tolerance(observed, outcome):
    assert compare(criterion(), observed, "percent").outcome == outcome


def test_boundary_is_exact_where_binary_floats_are_not():
    assert abs(94.1 - 94.2) > 0.1  # the trap
    assert compare(criterion(tolerance=0.1), 94.1, "percent").outcome == "within"


def test_zero_tolerance():
    assert compare(criterion(tolerance=0), 94.2, "percent").outcome == "within"
    assert compare(criterion(tolerance=0), 94.21, "percent").outcome == "outside"


@pytest.mark.parametrize(
    ("direction", "observed", "outcome"),
    [
        ("at_least", 99.0, "within"), ("at_least", 93.7, "within"), ("at_least", 93.6, "outside"),
        ("at_most", 10.0, "within"), ("at_most", 94.7, "within"), ("at_most", 94.8, "outside"),
    ],
)
def test_direction(direction, observed, outcome):
    assert compare(criterion(direction=direction), observed, "percent").outcome == outcome


def test_fraction_is_converted_to_the_criterion_unit():
    result = compare(criterion(), 0.937, "fraction")
    assert (result.outcome, result.observed, result.difference) == ("within", 93.7, -0.5)
    fractional = criterion(expected=0.942, unit="fraction", tolerance=0.005)
    assert compare(fractional, 92.1, "percent").outcome == "outside"


def test_units_are_not_guessed():
    assert compare(criterion(), 0.942, "percent").outcome == "outside"
    assert compare(criterion(), 94.2, "raw").outcome == "incomparable"


def test_missing_value():
    result = compare(criterion(), None, "percent")
    assert (result.outcome, result.observed, result.difference) == ("missing", None, None)
