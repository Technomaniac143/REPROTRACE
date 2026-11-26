import struct
from datetime import timedelta
from decimal import Decimal

import pytest
from conftest import END, START, make_observation, make_run, make_spec

from reprotrace.evidence.hashing import sha256_bytes
from reprotrace.verification.integrity import (
    _contains,
    check_output_created,
    check_value_in_source,
    check_value_not_in_inputs,
)

CRITERION = make_spec().criteria[0]  # expects 94.2 percent


@pytest.fixture
def scan(tmp_path):
    """Write input files, then scan them for the claimed and observed values."""

    def run_scan(files, read=(), observed=94.13):
        inventory = []
        for path, content in files.items():
            data = content if isinstance(content, bytes) else content.encode()
            (tmp_path / path).write_bytes(data)
            inventory.append({"path": path, "sha256": sha256_bytes(data)})
        run = make_run(input_files=inventory, files_read=read)
        return check_value_not_in_inputs(
            run, CRITERION, make_observation(value=observed), tmp_path
        )

    return run_scan


# Computed versus copied


def test_computed_result_is_not_flagged(scan):
    assert scan({"train.py": "print(evaluate(model))"}, read=["train.py"]).result == "pass"


@pytest.mark.parametrize(
    "line", ["acc = 94.2", "acc = 0.942", "acc = .942", "acc = 94.20", "print('94.2%')",
             "acc = 94.13", "acc = 0.9413"],
)
def test_hard_coded_result_is_flagged(scan, line):
    check = scan({"train.py": line}, read=["train.py"])
    assert check.result == "flagged"
    assert "train.py" in check.evidence[0]


@pytest.mark.parametrize("content", ['{"accuracy": 94.2}', struct.pack("<d", 94.13)])
def test_result_read_from_a_saved_file_is_flagged(scan, content):
    assert scan({"saved.bin": content}, read=["saved.bin"]).result == "flagged"


def test_source_counts_even_if_not_seen_to_be_read(scan):
    assert scan({"train.py": "acc = 94.2"}, read=[]).result == "flagged"


def test_value_in_an_unread_file_is_noted_not_flagged(scan):
    check = scan({"README.md": "94.2% accuracy"}, read=[])
    assert check.result == "pass"
    assert "README.md" in check.evidence[0]


# Not being able to tell is never a pass


def test_inconclusive_cases(scan, tmp_path):
    assert scan({"README.md": "94.2%"}, read=None).result == "inconclusive"  # reads unrecorded
    assert scan({}, read=[]).result == "inconclusive"  # no inventory
    absent = make_run(input_files=[{"path": "gone.py", "sha256": "a" * 64}])
    check = check_value_not_in_inputs(absent, CRITERION, make_observation(), tmp_path)
    assert check.result == "inconclusive"
    (tmp_path / "gone.py").write_text("changed since the run")
    check = check_value_not_in_inputs(absent, CRITERION, make_observation(), tmp_path)
    assert check.result == "inconclusive"


def test_low_precision_hit_is_inconclusive(scan):
    check = scan({"train.py": "momentum = 0.95"}, read=["train.py"], observed=95.0)
    assert check.result == "inconclusive"


@pytest.mark.parametrize(
    "text", [b"194.2", b"94.21", b"94.2.1", b"94.2e-1", b"0.9421", b"10.942", b"x"]
)
def test_other_numbers_do_not_match(text):
    assert not _contains(text, Decimal("94.2"))
    assert not _contains(text, Decimal("0.942"))


def test_scientific_notation_is_found():
    assert _contains(b"loss 1.25e-07", Decimal(repr(1.25e-07)))


# Output times and sources


def outputs(**file):
    return make_run(outputs=[{"path": "metrics.json", "sha256": "a" * 64} | file])


@pytest.mark.parametrize(
    ("run", "result"),
    [
        (outputs(created_at=END), "pass"),
        (outputs(created_at=START), "pass"),
        (outputs(created_at=START - timedelta(seconds=1)), "flagged"),
        (outputs(created_at=END + timedelta(seconds=1)), "flagged"),
        (outputs(), "inconclusive"),
        (make_run(outputs=[]), "inconclusive"),
        # Created during the run, but byte-identical to a file that was already there.
        (make_run(input_files=[{"path": "old.json", "sha256": "a" * 64}]), "flagged"),
    ],
)
def test_output_created_during_run(run, result):
    assert check_output_created(run, make_observation()).result == result


def test_observed_value_must_be_in_its_source(tmp_path):
    path = tmp_path / "metrics.json"
    path.write_bytes(b'{"accuracy": 92.1}')
    sha = sha256_bytes(path.read_bytes())

    def result(value, sha256=sha):
        observation = make_observation(value=value, source_sha256=sha256)
        return check_value_in_source(make_run(), observation, path).result

    assert result(92.1) == "pass"
    assert result(94.2) == "flagged"  # reported number is not the recorded one
    assert result(None) == "inconclusive"
    assert result(92.1, "0" * 64) == "inconclusive"
