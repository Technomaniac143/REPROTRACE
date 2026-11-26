"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from .evidence.ledger import LedgerError
from .orchestrator.recorded_audit import AuditError, run_recorded_audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reprotrace")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="turn recorded evidence into a claim report")
    audit.add_argument("bundle", type=Path, help="directory holding bundle.json and files/")
    audit.add_argument("--out", type=Path, help="new output directory (default: evidence/<time>)")
    args = parser.parse_args(argv)

    out = args.out or Path("evidence") / datetime.now(UTC).strftime("audit-%Y%m%dT%H%M%S%fZ")
    try:
        result = run_recorded_audit(args.bundle, out)
    except (AuditError, LedgerError, ValidationError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for verdict in result.verdicts:
        print(f"{verdict.claim_id}: {verdict.status} ({', '.join(verdict.reason_codes)})")
    print(f"report: {result.report_path}")
    return 0
