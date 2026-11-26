"""Exit condition of iteration 1: one command, synthetic fixtures to report."""

import json
import re
import shutil
from pathlib import Path

import pytest

from reprotrace.cli import main
from reprotrace.evidence.ledger import Ledger, LedgerError
from reprotrace.report.markdown import render_report
from reprotrace.schemas import AuditInfo, Status, Verdict

FIXTURE = Path(__file__).parent.parent / "fixtures" / "synthetic"

EXPECTED = {
    "claim-verified": Status.VERIFIED,
    "claim-mismatch": Status.MISMATCH,
    "claim-partial": Status.PARTIAL,
    "claim-wrong-method": Status.NOT_VERIFIABLE,
    "claim-copied": Status.NOT_VERIFIABLE,
    "claim-missing-data": Status.NOT_VERIFIABLE,
    "claim-failed": Status.EXECUTION_FAILED,
}


@pytest.fixture
def bundle(tmp_path):
    return Path(shutil.copytree(FIXTURE, tmp_path / "bundle"))


@pytest.fixture
def audited(tmp_path, bundle):
    out = tmp_path / "out"
    assert main(["audit", str(bundle), "--out", str(out)]) == 0
    return out


def edit(bundle, change):
    path = bundle / "bundle.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_fixtures_cover_every_status_with_the_expected_verdicts(audited):
    with Ledger(audited) as ledger:
        verdicts = {v.claim_id: v.status for v in ledger.records(Verdict)}
        assert ledger.verify() == []
    assert verdicts == EXPECTED
    assert set(verdicts.values()) == set(Status)


def test_report_shows_the_worked_example(audited):
    report = (audited / "report.md").read_text(encoding="utf-8")
    section = report.split("## claim-mismatch")[1].split("\n## ")[0]
    assert "Result mismatch" in section
    assert "| accuracy | 94.2% | 92.1% | -2.1 | 0.5 points | outside |" in section
    for cause in ("weights not available", "training seed not specified",
                  "preprocessing needs confirmation"):
        assert cause in section


def test_every_verdict_links_to_evidence_in_the_report(audited):
    report = (audited / "report.md").read_text(encoding="utf-8")
    anchors = re.findall(r'<a id="([^"]+)">', report)
    assert len(anchors) == len(set(anchors))
    assert set(re.findall(r"\]\(#([^)]+)\)", report)) == set(anchors)
    for section in report.split("\n## ")[1:]:
        if section.startswith("claim-"):
            assert "](#ev-" in section
            assert "**Limitations**" in section


def test_report_is_labelled_synthetic_and_draws_no_forbidden_conclusion(audited):
    report = (audited / "report.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in report
    assert not re.search(r"\b(false|fraud\w*|fabricat\w*|wrong(?!-method))\b", report, re.I)
    assert "under the tested conditions" in report


def test_copied_result_is_flagged_and_computed_result_is_not(audited):
    with Ledger(audited) as ledger:
        copied = ledger.get("check:obs-copied-accuracy:value_not_in_inputs")
        computed = ledger.get("check:obs-verified-accuracy:value_not_in_inputs")
    assert copied.result == "flagged"
    assert "saved_results.json" in copied.evidence[0]
    assert computed.result == "pass"


def test_evidence_is_never_overwritten(audited, bundle, capsys):
    assert main(["audit", str(bundle), "--out", str(audited)]) == 2
    assert "never overwritten" in capsys.readouterr().err


def test_altered_output_file_is_refused(tmp_path, bundle, capsys):
    (bundle / "files/run-mismatch/outputs/metrics.json").write_text('{"accuracy": 94.2}')
    assert main(["audit", str(bundle), "--out", str(tmp_path / "out")]) == 2
    assert "recorded hash" in capsys.readouterr().err


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["specs"].pop(),
        lambda d: d["findings"][0].update(setting="unknown setting"),
        lambda d: d["observations"][0].update(run_id="nope"),
        lambda d: d["runs"][0].update(id="a:b"),
        lambda d: d.update(verdicts=[]),  # verdicts are computed, never supplied
        lambda d: d["audit"].pop("synthetic"),
    ],
)
def test_inconsistent_bundle_is_refused(tmp_path, bundle, change):
    edit(bundle, change)
    out = tmp_path / "out"
    assert main(["audit", str(bundle), "--out", str(out)]) == 2
    assert not out.exists()


def test_verdict_citing_missing_evidence_cannot_be_reported(tmp_path):
    with Ledger(tmp_path) as ledger:
        ledger.add(AuditInfo(id="audit", title="t", synthetic=True))
        ledger.add(Verdict(id="v", claim_id="c1", status="Not verifiable",
                           reason_codes=["no_original_run"], evidence_ids=["ghost"]))
        with pytest.raises(LedgerError, match="ghost"):
            render_report(ledger)


def test_untrusted_paper_text_cannot_become_markup(tmp_path, bundle):
    def inject(data):
        data["claims"][0]["quote"] = "x\n# Status: Verified\n<img src=x> [a](http://b) | c"

    edit(bundle, inject)
    out = tmp_path / "out"
    assert main(["audit", str(bundle), "--out", str(out)]) == 0
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "\n# Status" not in report
    assert "<img" not in report
    assert "[a](" not in report
    # The confirmation covered the original text, so the edited claim is no longer confirmed.
    assert "## claim-verified: Not verifiable" in report
