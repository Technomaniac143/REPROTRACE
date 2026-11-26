import sqlite3

import pytest
from conftest import make_case, make_claim, make_run

from reprotrace.evidence.ledger import Ledger, LedgerError
from reprotrace.schemas import AuditInfo, RunRecord
from reprotrace.verification.verdict import decide


@pytest.fixture
def ledger(tmp_path):
    with Ledger(tmp_path / "ledger") as ledger:
        yield ledger


def tamper(tmp_path, sql):
    """Change the database behind the API's back, triggers removed."""
    db = sqlite3.connect(tmp_path / "ledger" / "ledger.sqlite")
    db.execute("DROP TRIGGER records_no_update")
    db.execute("DROP TRIGGER records_no_delete")
    db.execute(sql)
    db.commit()
    db.close()


def test_every_record_kind_round_trips(ledger):
    case = make_case()
    records = [
        AuditInfo(id="audit", title="t", synthetic=True), case.claim, case.spec, *case.artifacts,
        *case.findings, *case.approvals, *case.runs, *case.observations, *case.checks,
        decide(case),
    ]
    for record in records:
        ledger.add(record)
    assert ledger.records() == records
    assert [ledger.get(r.id) for r in records] == records
    assert ledger.records(RunRecord) == list(case.runs)
    assert ledger.verify() == []


def test_records_persist_after_reopening(tmp_path):
    with Ledger(tmp_path / "l") as ledger:
        ledger.add(make_run())
    with Ledger(tmp_path / "l") as ledger:
        assert ledger.get("r1") == make_run()
        assert ledger.verify() == []


def test_altering_or_removing_a_stored_file_is_detected(ledger, tmp_path):
    source = tmp_path / "metrics.json"
    source.write_text('{"accuracy": 92.1}')
    digest = ledger.add_file(source)
    assert ledger.verify() == []
    ledger.file_path(digest).write_text('{"accuracy": 94.2}')
    assert ledger.verify() == [f"file {digest}: content changed"]
    ledger.file_path(digest).unlink()
    assert ledger.verify() == [f"file {digest}: missing"]


def test_file_not_matching_its_recorded_hash_is_refused(ledger, tmp_path):
    source = tmp_path / "x"
    source.write_text("x")
    with pytest.raises(LedgerError):
        ledger.add_file(source, "0" * 64)


def test_there_is_no_update_or_delete(ledger, tmp_path):
    ledger.add(make_run())
    with pytest.raises(LedgerError):
        ledger.add(make_run(command="python other.py"))
    public = {n for n in dir(ledger) if not n.startswith("_")}
    assert public == {"add", "add_file", "close", "file_path", "get", "head_hash", "records",
                      "verify"}
    db = sqlite3.connect(tmp_path / "ledger" / "ledger.sqlite")
    for sql in ("UPDATE records SET body = '{}'", "DELETE FROM records"):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute(sql)
    db.close()
    assert ledger.get("r1") == make_run()


def test_edited_record_is_detected(ledger, tmp_path):
    ledger.add(make_run())
    tamper(tmp_path, "UPDATE records SET body = replace(body, 'train.py', 'other.py')")
    assert ledger.verify() == ["record r1: hash chain broken"]


def test_removed_record_is_detected(ledger, tmp_path):
    ledger.add(make_claim())
    ledger.add(make_run())
    tamper(tmp_path, "DELETE FROM records WHERE id = 'c1'")
    assert ledger.verify() == ["record r1: hash chain broken"]


def test_unknown_id_and_unknown_kind_are_errors(ledger):
    with pytest.raises(LedgerError):
        ledger.get("nope")
    with pytest.raises(LedgerError):
        ledger.add(make_run().limits)
