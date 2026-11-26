"""Deterministic metric comparison with a per-claim tolerance.

Decimal arithmetic keeps the boundary exact: in binary floats 94.2 - 94.1 is above 0.1.
Units are never guessed from a number's size.
"""

from decimal import Decimal

from ..schemas import Comparison, Criterion, Direction, Unit


def to_decimal(value: float) -> Decimal:
    return Decimal(repr(value))


def convert(value: Decimal, source: Unit, target: Unit) -> Decimal | None:
    """Return None when the units are not comparable."""
    if source == target:
        return value
    if (source, target) == (Unit.FRACTION, Unit.PERCENT):
        return value * 100
    if (source, target) == (Unit.PERCENT, Unit.FRACTION):
        return value / 100
    return None


def compare(criterion: Criterion, observed: float | None, unit: Unit) -> Comparison:
    def result(outcome, value=None, difference=None):
        return Comparison(
            metric=criterion.metric,
            expected=criterion.expected,
            observed=None if value is None else float(value),
            unit=criterion.unit,
            tolerance=criterion.tolerance,
            outcome=outcome,
            difference=None if difference is None else float(difference),
        )

    if observed is None:
        return result("missing")
    value = convert(to_decimal(observed), unit, criterion.unit)
    if value is None:
        return result("incomparable")

    difference = value - to_decimal(criterion.expected)
    tolerance = to_decimal(criterion.tolerance)
    within = {
        Direction.TWO_SIDED: abs(difference) <= tolerance,
        Direction.AT_LEAST: difference >= -tolerance,
        Direction.AT_MOST: difference <= tolerance,
    }[criterion.direction]
    return result("within" if within else "outside", value, difference)
