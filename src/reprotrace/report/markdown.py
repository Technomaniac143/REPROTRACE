"""Claim-level evidence report in Markdown, rendered from the ledger alone."""

from __future__ import annotations

import html
import re
from collections import Counter

from ..evidence.hashing import record_hash
from ..evidence.ledger import Ledger
from ..schemas import (
    Approval,
    ArtifactRecord,
    AuditInfo,
    Claim,
    Comparison,
    ConsistencyFinding,
    ExperimentSpec,
    IntegrityCheck,
    MetricObservation,
    RunRecord,
    SourceLocation,
    Status,
    StoredRecord,
    Unit,
    Verdict,
)

_CONCLUSIONS = {
    Status.VERIFIED: "The claim was reproduced under the tested conditions.",
    Status.PARTIAL: "Part of the claim was reproduced under the tested conditions.",
    Status.MISMATCH: "The claim was not reproduced under the tested conditions and needs "
    "investigation. A difference can have several explanations and is not a judgement on the "
    "paper or its authors.",
    Status.NOT_VERIFIABLE: "The available evidence does not allow a conclusion in either "
    "direction.",
    Status.EXECUTION_FAILED: "The run did not complete, so the claim was not tested. This is an "
    "execution outcome, not a scientific one.",
}


def _esc(text: object) -> str:
    """Papers and repositories are untrusted, so their text must not become markup."""
    flat = " ".join(str(text).split())
    return re.sub(r"([\\`*_{}\[\]()#|!~])", r"\\\1", html.escape(flat, quote=False))


def _anchor(id_: str) -> str:
    return "ev-" + re.sub(r"[^A-Za-z0-9-]", "-", id_)


def _link(id_: str) -> str:
    return f"[{_esc(id_)}](#{_anchor(id_)})"


def _location(source: SourceLocation) -> str:
    parts = []
    if source.page is not None:
        parts.append(f"page {source.page}")
    if source.table is not None:
        parts.append(f"table {source.table}")
    if source.section is not None:
        parts.append(f"section {source.section}")
    return _esc(", ".join(parts))


def _number(value: float, unit: Unit) -> str:
    return f"{value:.12g}%" if unit is Unit.PERCENT else f"{value:.12g}"


def _comparison_row(c: Comparison) -> str:
    observed = "not observed" if c.observed is None else _number(c.observed, c.unit)
    difference = "" if c.difference is None else f"{c.difference:+.12g}"
    points = " points" if c.unit is Unit.PERCENT else ""  # absolute, not relative
    return (
        f"| {_esc(c.metric)} | {_number(c.expected, c.unit)} | {observed} | {difference} "
        f"| {c.tolerance:.12g}{points} | {c.outcome} |"
    )


def _summary(record: StoredRecord) -> str:
    match record:
        case Claim():
            return f"Claim at {_location(record.source)}"
        case ExperimentSpec():
            frozen = record.frozen_at.isoformat() if record.frozen_at else "never"
            return f"Experiment spec, frozen {frozen}, hash `{record.content_hash}`"
        case ArtifactRecord():
            identity = record.commit or record.sha256 or "no identifier"
            return (
                f"{record.kind} artifact, {record.availability}, {_esc(record.location)}, "
                f"{_esc(identity)}"
            )
        case ConsistencyFinding():
            return (
                f"{record.stage} check of {_esc(record.setting)}: {record.result}, "
                f"{_esc(record.location)}"
            )
        case Approval():
            return f"User approval, {_esc(record.gate)}, {record.approved_at.isoformat()}"
        case RunRecord():
            outcome = "completed" if record.completed else f"failed ({record.failure_cause})"
            files = ", ".join(
                f"{_esc(f.path)} `{f.sha256}`" for f in (record.log, *record.outputs)
            )
            return (
                f"{record.kind} run, {_esc(outcome)}, {record.started_at.isoformat()} to "
                f"{record.ended_at.isoformat()}, command {_esc(record.command)}, "
                f"image {_esc(record.image_digest)}, files: {files}"
            )
        case MetricObservation():
            value = "no value" if record.value is None else _number(record.value, record.unit)
            return (
                f"{_esc(record.metric)} = {value}, from {_esc(record.source_path)} "
                f"`{record.source_sha256}`"
            )
        case IntegrityCheck():
            return (
                f"Integrity check {_esc(record.name)}: {record.result}. "
                f"{_esc('; '.join(record.evidence))}. Limit: {_esc(record.limitation)}"
            )
    raise TypeError(f"not evidence: {type(record).__name__}")


def _bullets(title: str, items: tuple[str, ...]) -> list[str]:
    return [f"**{title}**", "", *(f"- {_esc(i)}" for i in items), ""] if items else []


def render_report(ledger: Ledger) -> str:
    (audit,) = ledger.records(AuditInfo)
    verdicts: list[Verdict] = ledger.records(Verdict)
    claims: dict[str, Claim] = {c.id: c for c in ledger.records(Claim)}
    # `get` raises for an unknown id, so a verdict citing missing evidence cannot be reported.
    cited = {i: ledger.get(i) for v in verdicts for i in v.evidence_ids}

    out = [f"# Evidence report: {_esc(audit.title)}", ""]
    if audit.synthetic:
        out += ["> **SYNTHETIC DATA. This is not an audit of a real paper.**", ""]
    out += ["| Status | Claims |", "|---|---|"]
    counts = Counter(v.status for v in verdicts)
    out += [f"| {s.value} | {counts[s]} |" for s in Status if counts[s]]
    out.append("")

    for v in verdicts:
        claim = claims[v.claim_id]
        out += [
            f"## {_esc(claim.id)}: {v.status.value}",
            "",
            f"> {_esc(claim.quote)}",
            "",
            f"Source: {_location(claim.source)}. Claimed {_esc(claim.metric)}: "
            f"{_number(claim.value, claim.unit)} ({_esc(claim.model)} on {_esc(claim.dataset)}).",
            "",
            f"**Reason:** {_esc(', '.join(v.reason_codes))}"
            + (f" (cause: {_esc(v.failure_cause)})" if v.failure_cause else ""),
            "",
            f"**Conclusion:** {_CONCLUSIONS[v.status]}",
            "",
        ]
        if v.comparisons:
            out += [
                "| Metric | Claimed | Observed | Difference | Tolerance | Outcome |",
                "|---|---|---|---|---|---|",
                *map(_comparison_row, v.comparisons),
                "",
            ]
        out += _bullets("Possible causes, from recorded gaps (not a diagnosis)", v.possible_causes)
        out += _bullets("Limitations", v.limitations)
        out += ["**Evidence**", "", ", ".join(_link(i) for i in v.evidence_ids), ""]

    out += [
        "## Limits of this report",
        "",
        "- Conclusions hold only under the tested conditions.",
        "- They cannot establish that a hypothesis is true, that a study is free of bias, or "
        "how its authors acted.",
        "- Integrity checks reduce the chance of accepting a copied number. None is proof alone.",
        "",
        "## Evidence index",
        "",
        f"Ledger head `{ledger.head_hash}`",
        "",
    ]
    for id_, record in cited.items():
        out.append(
            f'- <a id="{_anchor(id_)}"></a>**{_esc(id_)}** (record `{record_hash(record)}`): '
            f"{_summary(record)}"
        )
    return "\n".join(out) + "\n"
