"""Self-contained HTML dashboard for one audit, rendered from the ledger alone.

Like the Markdown report, it reads nothing but the ledger, so it shows exactly the evidence
the verdicts rest on. Every string from a paper, repository or bundle is escaped: that text is
untrusted and must never become markup or script. The page loads nothing from the network.
"""

from __future__ import annotations

import html
from collections import Counter

from ..evidence.hashing import record_hash
from ..evidence.ledger import Ledger
from ..report.markdown import _CONCLUSIONS, _number
from ..schemas import (
    Approval,
    ArtifactRecord,
    AuditInfo,
    CheckResult,
    Claim,
    Comparison,
    ConsistencyFinding,
    Criterion,
    Direction,
    ExperimentSpec,
    Gate,
    IntegrityCheck,
    RunKind,
    RunRecord,
    SourceLocation,
    Status,
    Verdict,
)

_STATUS_CLASS = {
    Status.VERIFIED: "verified",
    Status.PARTIAL: "partial",
    Status.MISMATCH: "mismatch",
    Status.NOT_VERIFIABLE: "notverifiable",
    Status.EXECUTION_FAILED: "failed",
}

_CHECK_LABEL = {
    "output_created_during_run": "Metric file created during the run",
    "value_found_in_source": "Value found in the recorded output",
    "value_not_in_inputs": "Value absent from pre-run inputs",
}

_CHECK_MARK = {CheckResult.PASS: "pass", CheckResult.FLAGGED: "flag", CheckResult.INCONCLUSIVE: "n/a"}


def _h(text: object) -> str:
    return html.escape(str(text), quote=True)


def _anchor(id_: str) -> str:
    return "ev-" + "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in id_)


def _location(source: SourceLocation | None) -> str:
    if source is None:
        return ""
    parts = []
    if source.page is not None:
        parts.append(f"p. {source.page}")
    if source.table is not None:
        parts.append(f"table {source.table}")
    if source.section is not None:
        parts.append(f"§{source.section}")
    return ", ".join(parts)


def _gauge(c: Comparison, criterion: Criterion | None) -> str:
    """Claimed value, tolerance band and observed value on one thin scale."""
    e, t = c.expected, c.tolerance
    diff = 0.0 if c.observed is None else c.observed - e
    span = max(3 * t, 1.4 * abs(diff), 0.05)
    low, high = e - span, e + span

    def pos(x: float) -> float:
        return max(0.0, min(100.0, (x - low) / (high - low) * 100))

    direction = criterion.direction if criterion else Direction.TWO_SIDED
    band_lo = e - t if direction is not Direction.AT_MOST else low
    band_hi = e + t if direction is not Direction.AT_LEAST else high
    observed = (
        ""
        if c.observed is None
        else f'<i class="obs {_h(c.outcome)}" style="left:{pos(c.observed):.2f}%"></i>'
    )
    return (
        f'<div class="scale" role="img" aria-label="{_h(c.metric)}: claimed '
        f'{_number(e, c.unit)}, observed '
        f'{"none" if c.observed is None else _number(c.observed, c.unit)}">'
        f'<i class="band" style="left:{pos(band_lo):.2f}%;width:{pos(band_hi) - pos(band_lo):.2f}%">'
        f'</i><i class="exp" style="left:{pos(e):.2f}%"></i>{observed}'
        f'<span class="lo">{low:.4g}</span><span class="hi">{high:.4g}</span></div>'
    )


def _figures(c: Comparison, criterion: Criterion | None) -> str:
    direction = criterion.direction if criterion else Direction.TWO_SIDED
    tol = f"± {c.tolerance:.4g}" if direction is Direction.TWO_SIDED else (
        f"{c.tolerance:.4g} {direction.value.replace('_', ' ')}"
    )
    observed = "—" if c.observed is None else _number(c.observed, c.unit)
    delta = "—" if c.difference is None else f"{c.difference:+.4g}"
    return (
        f'<dl class="figures"><dt>Claimed</dt><dd>{_number(c.expected, c.unit)}</dd>'
        f'<dt>Observed</dt><dd class="{_h(c.outcome)}">{_h(observed)}</dd>'
        f"<dt>Difference</dt><dd>{_h(delta)}</dd><dt>Tolerance</dt><dd>{_h(tol)}</dd>"
        f'<dt>Outcome</dt><dd class="{_h(c.outcome)}">{_h(c.outcome)}</dd></dl>'
    )


def _settings(spec: ExperimentSpec, findings: list[ConsistencyFinding]) -> str:
    rows = []
    for s in spec.settings:
        found = {f.stage.value: f for f in findings if f.setting == s.name}

        def cell(stage: str) -> str:
            f = found.get(stage)
            if f is None:
                return '<td class="quiet">—</td>'
            return f'<td class="r-{_h(f.result)}" title="{_h(f.location)}">{_h(f.result)}</td>'

        rows.append(
            f"<tr><td>{_h(s.name)}{'<sup>M</sup>' if s.material else ''}</td>"
            f'<td class="s-{_h(s.status)}">{_h(s.status)}</td>'
            f"<td>{_h(s.value or '—')}</td><td class=quiet>{_h(_location(s.source))}</td>"
            f"{cell('implementation')}{cell('execution')}</tr>"
        )
    return (
        "<table><thead><tr><th>Setting</th><th>Paper</th><th>Value</th><th>Source</th>"
        "<th>Code</th><th>Run</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table><p class=foot><sup>M</sup> material: must be shown to match "
        "before a claim can be Verified.</p>"
    )


def _checks(checks: list[IntegrityCheck]) -> str:
    if not checks:
        return '<p class="quiet">None run: no metric was observed.</p>'
    items = "".join(
        f'<li><span class="mark m-{_h(c.result)}">{_CHECK_MARK[c.result]}</span>'
        f"<div>{_h(_CHECK_LABEL.get(c.name, c.name))}"
        f'<small>{_h("; ".join(c.evidence))}</small></div></li>'
        for c in checks
    )
    return f'<ul class="checks">{items}</ul>'


def _list(title: str, items: tuple[str, ...]) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{_h(i)}</li>" for i in items)
    return f"<section><h4>{_h(title)}</h4><ul class=plain>{lis}</ul></section>"


def _card(n: int, v: Verdict, ledger: Ledger) -> str:
    claim: Claim = ledger.get(v.claim_id)
    spec = next(s for s in ledger.records(ExperimentSpec) if s.claim_id == claim.id)
    runs = {r.id for r in ledger.records(RunRecord) if r.claim_id == claim.id}
    checks = [c for c in ledger.records(IntegrityCheck) if c.run_id in runs]
    findings = [f for f in ledger.records(ConsistencyFinding) if f.claim_id == claim.id]
    criteria = {c.metric: c for c in spec.criteria}
    cls = _STATUS_CLASS[v.status]

    if v.comparisons:
        measure = "".join(
            _gauge(c, criteria.get(c.metric)) + _figures(c, criteria.get(c.metric))
            for c in v.comparisons
        )
    else:
        measure = (
            f'<dl class="figures"><dt>Claimed</dt><dd>{_number(claim.value, claim.unit)}</dd>'
            '<dt>Observed</dt><dd>—</dd></dl><p class="quiet small">No comparison: the '
            "verdict was reached before the metric could be compared.</p>"
        )
    reasons = ", ".join(f"<code>{_h(r)}</code>" for r in v.reason_codes)
    if v.failure_cause:
        reasons += f", cause <code>{_h(v.failure_cause)}</code>"
    evidence = " ".join(
        f'<a href="#{_anchor(i)}">{_h(i)}</a>' for i in v.evidence_ids
    )
    spec_hash = (spec.content_hash or "not frozen")[:12]
    return f"""
<article class="card {cls}" data-status="{cls}" id="card-{_h(_anchor(claim.id)[3:])}">
  <div class="aside">
    <span class="num">{n:02d}</span>
    <span class="status"><i></i>{_h(v.status.value)}</span>
    <code class="cid">{_h(claim.id)}</code>
    <span class="quiet small">{_h(_location(claim.source))}</span>
  </div>
  <div class="body">
    <blockquote>{_h(claim.quote)}</blockquote>
    <p class="meta">{_h(claim.model)} &middot; {_h(claim.dataset)} &middot; {_h(claim.metric)}</p>
    <p class="conclusion">{_h(_CONCLUSIONS[v.status])}</p>
    <p class="reasons">Reason: {reasons}</p>
    <details>
      <summary>Evidence trail</summary>
      <div class="trail">
        <section><h4>Experiment spec <code>{_h(spec_hash)}</code></h4>
          {_settings(spec, findings)}</section>
        <section><h4>Computed, not copied</h4>{_checks(checks)}</section>
        {_list("Possible causes, from recorded gaps (not a diagnosis)", v.possible_causes)}
        {_list("Limitations", v.limitations)}
        <section><h4>Cited records ({len(v.evidence_ids)})</h4>
          <p class="cites">{evidence}</p></section>
      </div>
    </details>
  </div>
  <div class="measure">{measure}</div>
</article>"""


def _pipeline(ledger: Ledger) -> str:
    claims = ledger.records(Claim)
    specs = ledger.records(ExperimentSpec)
    approvals = ledger.records(Approval)
    runs = [r for r in ledger.records(RunRecord) if r.kind is RunKind.ORIGINAL]
    stages = [
        ("Claim cards", f"{len(claims)}", False),
        ("Gate 1", f"{sum(c.confirmed_by_user for c in claims)} confirmed", False),
        ("Spec frozen", f"{sum(s.content_hash is not None for s in specs)} hashed", False),
        ("Artifact audit", f"{len(ledger.records(ConsistencyFinding))} findings", False),
        ("Gate 2", f"{sum(a.gate is Gate.RUN for a in approvals)} approved", False),
        ("Original run", f"{sum(r.completed for r in runs)} of {len(runs)} ran", False),
        ("Verification", f"{len(ledger.records(Verdict))} verdicts", True),
        ("Report", "ledger verified", True),
    ]
    items = "".join(
        f'<li class="{"live" if live else "rec"}"><span>{i:02d}</span><b>{_h(name)}</b>'
        f"<small>{_h(detail)}</small></li>"
        for i, (name, detail, live) in enumerate(stages, 1)
    )
    return (
        f'<ol class="pipeline">{items}</ol><p class="legend"><i class="live"></i>computed by '
        'this audit <i class="rec"></i>read from the recorded bundle</p>'
    )


def _summary(verdicts: list[Verdict]) -> str:
    counts = Counter(v.status for v in verdicts)
    total = len(verdicts) or 1
    bar = "".join(
        f'<i class="{_STATUS_CLASS[s]}" style="width:{counts[s] / total * 100:.3f}%"></i>'
        for s in Status
        if counts[s]
    )
    filters = "".join(
        f'<button data-filter="{_STATUS_CLASS[s]}" class="{_STATUS_CLASS[s]}"><i></i>'
        f"{_h(s.value)} <b>{counts[s]}</b></button>"
        for s in Status
        if counts[s]
    )
    return (
        f'<div class="summary"><div class="bar">{bar}</div><div class="filters">'
        f'<button data-filter="all" class="active">All claims <b>{len(verdicts)}</b></button>'
        f"{filters}</div></div>"
    )


def render_dashboard(ledger: Ledger) -> str:
    (audit,) = ledger.records(AuditInfo)
    verdicts: list[Verdict] = ledger.records(Verdict)
    notice = (
        '<p class="notice"><b>Synthetic data.</b> This is not an audit of a real paper. '
        "Claim cards and runs are recorded fixtures; verdicts and "
        "integrity checks are computed by the engine.</p>"
        if audit.synthetic
        else ""
    )
    cited = {i for v in verdicts for i in v.evidence_ids}
    index = "".join(
        f'<tr id="{_anchor(r.id)}"><td><code>{_h(r.id)}</code></td>'
        f"<td>{_h(type(r).__name__)}</td><td><code>{record_hash(r)[:16]}</code></td>"
        f"<td><details><summary>view</summary><pre>{_h(r.model_dump_json(indent=2))}</pre>"
        "</details></td></tr>"
        for r in ledger.records()
        if r.id in cited
    )
    cards = "".join(_card(n, v, ledger) for n, v in enumerate(verdicts, 1))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>REPROTRACE · {_h(audit.title)}</title>
<style>{_CSS}</style></head>
<body>
<header class="mast">
  <span class="word">REPROTRACE</span>
  <span class="quiet">Ledger <code>{ledger.head_hash[:12]}</code> &middot; chain intact</span>
</header>
<main>
  <p class="kicker">Evidence report</p>
  <h1>{_h(audit.title)}</h1>
  <p class="lead">Each claim is checked against a frozen experiment spec, recorded run evidence
    and integrity checks. Conclusions hold only under the tested conditions.</p>
  {notice}
  {_pipeline(ledger)}
  {_summary(verdicts)}
  <section class="claims">{cards}</section>
  <section class="index"><h2>Evidence index</h2>
    <table><thead><tr><th>Record</th><th>Type</th><th>SHA-256 (prefix)</th><th></th></tr>
    </thead><tbody>{index}</tbody></table></section>
  <p class="limits">Conclusions cannot establish that a hypothesis is true, that a study is
    free of bias, or how its authors acted. Integrity checks reduce the chance of accepting a
    copied number; none is proof alone.</p>
</main>
<script>{_JS}</script>
</body></html>
"""


_JS = """
document.querySelectorAll('.filters button').forEach(function (b) {
  b.addEventListener('click', function () {
    var f = b.dataset.filter;
    document.querySelectorAll('.filters button').forEach(function (x) {
      x.classList.toggle('active', x === b);
    });
    document.querySelectorAll('.card').forEach(function (c) {
      c.hidden = !(f === 'all' || c.dataset.status === f);
    });
  });
});
"""

_CSS = """
:root{--paper:#f6f4ef;--ink:#1c1b19;--soft:#55524b;--quiet:#8a857b;--rule:#d9d4c8;--hair:#e8e4da;
--tint:#efece4;--verified:#2e6f4e;--partial:#2f5f86;--mismatch:#a8571c;--notverifiable:#5f4b8b;
--failed:#a3342f;--serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
--sans:"Segoe UI","Helvetica Neue",Arial,sans-serif;--mono:"Cascadia Mono","SF Mono",Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--paper:#161514;--ink:#e9e5dc;--soft:#b9b3a6;--quiet:#857f73;
--rule:#3a3732;--hair:#2a2825;--tint:#1f1e1b;--verified:#6fb48d;--partial:#7fa9cf;--mismatch:#d99256;
--notverifiable:#a993d6;--failed:#e0726b}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--sans);
-webkit-font-smoothing:antialiased}
code,pre{font-family:var(--mono);font-size:.86em}
a{color:inherit}
.quiet{color:var(--quiet)}.small{font-size:13px}
.mast{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;
width:min(1056px,calc(100% - 64px));margin:0 auto;padding:22px 0 12px;border-bottom:2px solid var(--ink);
font-size:13px}
.word{font-weight:700;letter-spacing:.22em;font-size:13px}
main{width:min(1056px,calc(100% - 64px));margin:0 auto;padding:28px 0 64px}
.kicker{margin:0;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--quiet)}
h1{font-family:var(--serif);font-weight:400;font-size:42px;line-height:1.1;margin:6px 0 10px}
.lead{max-width:640px;color:var(--soft);margin:0 0 20px}
.notice{border-left:3px solid var(--mismatch);padding:2px 0 2px 14px;margin:0 0 28px;
color:var(--soft);font-size:13.5px;max-width:760px}.notice b{color:var(--ink)}
.pipeline{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(8,1fr);
border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.pipeline li{padding:10px 10px 12px;border-left:1px solid var(--hair);display:flex;flex-direction:column}
.pipeline li:first-child{border-left:0;padding-left:0}
.pipeline span{font:11px var(--mono);color:var(--quiet)}
.pipeline b{font-weight:600;font-size:13px;margin-top:2px}
.pipeline small{font-size:12px;color:var(--soft)}
.pipeline li.live span::after,.legend i.live{content:"";display:inline-block;width:7px;height:7px;
border-radius:50%;background:var(--ink);margin-left:6px;vertical-align:1px}
.pipeline li.rec span::after,.legend i.rec{content:"";display:inline-block;width:7px;height:7px;
border-radius:50%;border:1px solid var(--quiet);margin-left:6px;vertical-align:1px}
.legend{font-size:12px;color:var(--quiet);margin:8px 0 36px}.legend i{margin:0 5px 0 14px!important}
.legend i:first-child{margin-left:0!important}
.summary{margin-bottom:8px}
.bar{display:flex;height:6px;background:var(--hair)}.bar i{display:block;height:100%}
.bar i+i{border-left:2px solid var(--paper)}
.filters{display:flex;flex-wrap:wrap;gap:4px 22px;margin:12px 0 0}
.filters button{all:unset;cursor:pointer;font-size:13px;color:var(--soft);padding:2px 0;
border-bottom:1.5px solid transparent}
.filters button b{font:600 12px var(--mono);color:var(--ink);margin-left:4px}
.filters button i,.status i{display:inline-block;width:8px;height:8px;background:var(--c);margin-right:7px}
.filters button.active{color:var(--ink);border-bottom-color:var(--ink)}
.filters button:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
.verified{--c:var(--verified)}.partial{--c:var(--partial)}.mismatch{--c:var(--mismatch)}
.notverifiable{--c:var(--notverifiable)}.failed{--c:var(--failed)}
.bar i{background:var(--c)}
.claims{border-top:1px solid var(--ink);margin-top:28px}
.card{display:grid;grid-template-columns:170px minmax(0,1fr) 250px;gap:28px;padding:26px 0;
border-bottom:1px solid var(--rule)}
.card[hidden]{display:none}
.aside{display:flex;flex-direction:column;gap:6px}
.num{font:12px var(--mono);color:var(--quiet)}
.status{font-size:13px;font-weight:600;color:var(--c)}
.cid{font-size:12.5px;color:var(--soft)}
blockquote{margin:0;font-family:var(--serif);font-size:21px;line-height:1.35}
.meta{margin:8px 0 0;font-size:13px;color:var(--quiet)}
.conclusion{margin:14px 0 0;color:var(--soft);max-width:560px}
.reasons{margin:6px 0 0;font-size:13px;color:var(--quiet)}.reasons code{color:var(--ink)}
details summary{cursor:pointer;font-size:13px;font-weight:600;margin-top:14px;list-style:none;
display:inline-block;border-bottom:1px solid var(--ink)}
details summary::-webkit-details-marker{display:none}
details summary::after{content:" +";font-family:var(--mono)}
details[open]>summary::after{content:" \\2212"}
.trail{margin-top:16px;display:grid;gap:18px;padding-left:14px;border-left:1px solid var(--rule)}
h4{margin:0 0 6px;font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--quiet);
font-weight:600}h4 code{letter-spacing:0;text-transform:none;margin-left:6px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-weight:600;font-size:11.5px;color:var(--quiet);border-bottom:1px solid var(--rule);
padding:4px 8px 4px 0}td{padding:5px 8px 5px 0;border-bottom:1px solid var(--hair);vertical-align:top}
sup{font:600 9px var(--mono);color:var(--quiet);margin-left:2px}
.foot{font-size:11.5px;color:var(--quiet);margin:6px 0 0}
.s-inferred,.r-partial,.r-unknown{color:var(--mismatch)}.s-missing,.r-mismatch{color:var(--failed)}
.r-match{color:var(--verified)}
.checks{list-style:none;margin:0;padding:0;display:grid;gap:8px;font-size:13.5px}
.checks li{display:grid;grid-template-columns:44px 1fr;gap:8px}
.checks small{display:block;color:var(--quiet);font-size:12px;word-break:break-word}
.mark{font:600 11px var(--mono);text-transform:uppercase;padding-top:2px}
.m-pass{color:var(--verified)}.m-flagged{color:var(--failed)}.m-inconclusive{color:var(--quiet)}
.plain{margin:0;padding-left:18px;font-size:13.5px;color:var(--soft)}
.cites{margin:0;font:11.5px/1.9 var(--mono);color:var(--quiet)}
.cites a{color:var(--soft);text-decoration:none;border-bottom:1px dotted var(--quiet);margin-right:8px}
.cites a:hover{color:var(--ink)}
.measure{padding-top:4px}
.scale{position:relative;height:30px;margin-bottom:12px}
.scale::before{content:"";position:absolute;left:0;right:0;top:9px;height:1px;background:var(--rule)}
.scale i{position:absolute;display:block}
.scale .band{top:5px;height:9px;background:var(--tint);border-left:1px solid var(--soft);
border-right:1px solid var(--soft)}
.scale .exp{top:2px;width:1px;height:15px;background:var(--ink)}
.scale .obs{top:5px;width:9px;height:9px;margin-left:-4.5px;border-radius:50%;background:var(--verified)}
.scale .obs.outside{background:var(--mismatch)}
.scale span{position:absolute;top:17px;font:10.5px var(--mono);color:var(--quiet)}
.scale .lo{left:0}.scale .hi{right:0}
.figures{display:grid;grid-template-columns:auto 1fr;gap:3px 16px;margin:0;font-size:13px}
.figures dt{color:var(--quiet)}
.figures dd{margin:0;text-align:right;font:13px var(--mono);font-variant-numeric:tabular-nums}
.figures dd.within{color:var(--verified)}.figures dd.outside{color:var(--mismatch)}
.index{margin-top:56px}
.index h2{font-family:var(--serif);font-weight:400;font-size:26px;margin:0 0 12px}
.index summary{margin:0;font-weight:400;border-bottom-style:dotted}
pre{white-space:pre-wrap;margin:6px 0;font-size:11.5px;max-height:260px;overflow:auto;
background:var(--tint);padding:8px}
tr:target{background:var(--tint)}
.limits{margin-top:36px;font-size:12.5px;color:var(--quiet);max-width:720px}
@media (max-width:900px){.card{grid-template-columns:1fr;gap:14px}.aside{flex-direction:row;
flex-wrap:wrap;align-items:baseline;gap:4px 14px}.pipeline{grid-template-columns:repeat(4,1fr)}
.pipeline li:nth-child(5){border-left:0;padding-left:0}}
@media (max-width:560px){main,.mast{width:calc(100% - 32px)}h1{font-size:32px}
.pipeline{grid-template-columns:repeat(2,1fr)}.pipeline li:nth-child(odd){border-left:0;padding-left:0}}
"""
