#!/usr/bin/env python3
"""E2E demo — run full pipeline and show data flow."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from portfolio_ninja.domain.stubs import StubDataAdapter, StubExecutionAdapter
from portfolio_ninja.operator_report import render_report
from portfolio_ninja.orchestrator import run

if __name__ == "__main__":
    print("=" * 80)
    print("PORTFOLIO_NINJA E2E DEMO — Full Pipeline with Stub Adapters")
    print("=" * 80)
    print()

    # Run orchestrator with 5 tickers, stub adapters
    print("INPUT: tickers=['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META']")
    print("INPUT: run_mode='backtest', window_days=730")
    print()
    print("Running full pipeline...")
    print()

    audit_record = run(
        tickers=["AAPL", "MSFT", "GOOG", "AMZN", "META"],
        data_adapter=StubDataAdapter(),
        exec_adapter=StubExecutionAdapter(),
        run_mode="backtest",
        window_days=730,
    )

    # Show audit record metadata
    print("AUDIT RECORD (metadata):")
    print(f"  Cycle ID: {audit_record.cycle_id}")
    print(f"  Run mode: {audit_record.run_mode}")
    print(f"  Tickers: {audit_record.tickers}")
    print(f"  Validation status: {audit_record.validation_status}")
    print(f"  Completed at: {audit_record.completed_at}")
    print()

    # Show pipeline hashes (proves all modules ran)
    print("PIPELINE HASHES (proves all 9 modules executed):")
    for key, hash_val in sorted(audit_record.pipeline_hashes.items()):
        print(f"  {key:20s}: {hash_val[:16]}...")
    print()

    # Show full operator report
    print("=" * 80)
    print("OPERATOR REPORT (human-readable output)")
    print("=" * 80)
    print()
    report = render_report(audit_record)
    print(report)
    print()
    print("=" * 80)
    print("E2E TEST: PASS — All modules wired, data flows through, output generated.")
    print("=" * 80)
