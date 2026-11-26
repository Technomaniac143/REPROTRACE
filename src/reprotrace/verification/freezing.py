"""Spec freezing: criteria are fixed and hashed before a run (hard rule 9).

The hash covers everything except itself, including the freeze time. A spec edited and then
re-frozen gets a new hash, which no longer matches the one recorded in the run and approval.
"""

from datetime import datetime

from ..evidence.hashing import record_hash
from ..schemas import Claim, ExperimentSpec


def criteria_match_claim(spec: ExperimentSpec, claim: Claim) -> bool:
    """The claim's own number must be one of the criteria, so it cannot be swapped out."""
    return spec.claim_id == claim.id and any(
        c.metric == claim.metric and c.expected == claim.value and c.unit == claim.unit
        for c in spec.criteria
    )


def spec_hash(spec: ExperimentSpec) -> str:
    return record_hash(spec, exclude={"content_hash"})


def freeze(spec: ExperimentSpec, claim: Claim, at: datetime) -> ExperimentSpec:
    if spec.content_hash is not None:
        raise ValueError("spec is already frozen")
    if not criteria_match_claim(spec, claim):
        raise ValueError("no criterion matches the claim's metric, value and unit")
    data = spec.model_dump() | {"frozen_at": at, "content_hash": "0" * 64}
    stamped = ExperimentSpec.model_validate(data)
    return ExperimentSpec.model_validate(data | {"content_hash": spec_hash(stamped)})


def is_intact(spec: ExperimentSpec) -> bool:
    return spec.content_hash is not None and spec_hash(spec) == spec.content_hash
