"""The HTML dashboard: rendered from the ledger, labelled, escaped and offline."""

import json
import re
import shutil
from pathlib import Path

import pytest

from reprotrace.cli import main
from reprotrace.evidence.ledger import Ledger
from reprotrace.schemas import Verdict

FIXTURE = Path(__file__).parent.parent / "fixtures" / "synthetic"


@pytest.fixture
def bundle(tmp_path):
    return Path(shutil.copytree(FIXTURE, tmp_path / "bundle"))


def audit(tmp_path, bundle):
    out = tmp_path / "out"
    assert main(["audit", str(bundle), "--out", str(out)]) == 0
    return out, (out / "dashboard.html").read_text(encoding="utf-8")


def test_dashboard_shows_every_verdict_with_its_evidence(tmp_path, bundle):
    out, page = audit(tmp_path, bundle)
    with Ledger(out) as ledger:
        verdicts = ledger.records(Verdict)
    assert len(re.findall(r'<article class="card ', page)) == len(verdicts) == 7
    for v in verdicts:
        assert v.status.value in page
        for i in v.evidence_ids:
            # Each evidence link has a row in the evidence index.
            assert f'href="#ev-{re.sub(r"[^A-Za-z0-9-]", "-", i)}"' in page
            assert f'<tr id="ev-{re.sub(r"[^A-Za-z0-9-]", "-", i)}"' in page


def test_dashboard_is_labelled_synthetic_and_loads_nothing_remote(tmp_path, bundle):
    _, page = audit(tmp_path, bundle)
    assert "<b>Synthetic data.</b> This is not an audit of a real paper." in page
    assert "default-src 'none'" in page
    assert not re.search(r'(src|href)="https?:', page)


def test_dashboard_draws_no_forbidden_conclusion(tmp_path, bundle):
    _, page = audit(tmp_path, bundle)
    assert not re.search(r"\b(fraud|paper is false)\b", page, re.IGNORECASE)


def test_untrusted_text_cannot_become_markup_or_script(tmp_path, bundle):
    path = bundle / "bundle.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["claims"][0]["quote"] = '<script>alert(1)</script><img src=x onerror=alert(2)>"'
    path.write_text(json.dumps(data), encoding="utf-8")
    _, page = audit(tmp_path, bundle)
    assert "<script>alert" not in page
    assert "<img src=x" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.count("<script>") == 1  # only the page's own filter script
