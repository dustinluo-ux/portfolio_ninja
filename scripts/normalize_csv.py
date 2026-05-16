"""CLI: normalize all OHLCV CSV files in the trading data directory.

Usage:
    conda run -n portfolio_ninja python scripts/normalize_csv.py [options]

Options:
    --base-dir PATH    Root directory to scan (default: C:/portfolio_ninja/trading_data)
    --ticker TICKER    Normalize a single ticker's CSV only
    --dry-run          Report issues without modifying any files
    --verbose          Show per-file detail
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_ninja.data_plane.date_normalizer import (
    NormalizationReport,
    normalize_csv,
    normalize_directory,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DEFAULT_BASE = Path("C:/portfolio_ninja/trading_data")


def _print_report(report: NormalizationReport, verbose: bool) -> None:
    issues = []
    if report.future_removed:
        issues.append(f"future_removed={report.future_removed}")
    if report.duplicates_removed:
        issues.append(f"dupes_removed={report.duplicates_removed}")
    if report.sort_applied:
        issues.append("sorted")
    if report.ambiguous_dates:
        issues.append(f"ambiguous={len(report.ambiguous_dates)}")

    row_delta = report.rows_output - report.rows_input
    delta_str = f"{row_delta:+d}" if row_delta else "="

    if verbose or issues:
        print(
            f"{report.path.name:<20} "
            f"fmt={report.format_detected:<14} "
            f"conf={report.format_confidence:.2f}  "
            f"rows={report.rows_input}→{report.rows_output}({delta_str})  "
            + ("  ".join(issues) if issues else "OK")
        )


def _find_ticker_csv(base_dir: Path, ticker: str) -> list[Path]:
    ticker_upper = ticker.upper()
    return [p for p in base_dir.rglob(f"{ticker_upper}.csv")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize OHLCV CSV date formats")
    parser.add_argument("--base-dir", type=Path, default=_DEFAULT_BASE)
    parser.add_argument("--ticker", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    as_of = date.today()

    if args.dry_run:
        print("[DRY RUN] No files will be modified.\n")

    if args.ticker:
        paths = _find_ticker_csv(args.base_dir, args.ticker)
        if not paths:
            print(f"No CSV found for ticker {args.ticker!r} under {args.base_dir}")
            sys.exit(1)
        targets = paths
    else:
        targets = sorted(args.base_dir.rglob("*.csv"))

    print(f"Scanning {len(targets)} CSV file(s) under {args.base_dir}\n")

    total_future = 0
    total_dupes = 0
    total_sorted = 0
    total_ambiguous = 0
    errors = 0

    for csv_path in targets:
        if args.dry_run:
            # Read-only analysis: run normalize on a temp copy
            import shutil, tempfile
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copy2(csv_path, tmp_path)
            try:
                report = normalize_csv(tmp_path, as_of=as_of)
                report.path = csv_path  # show original path in report
            except Exception as exc:
                print(f"ERROR {csv_path.name}: {exc}")
                errors += 1
                tmp_path.unlink(missing_ok=True)
                continue
            finally:
                tmp_path.unlink(missing_ok=True)
        else:
            try:
                report = normalize_csv(csv_path, as_of=as_of)
            except Exception as exc:
                print(f"ERROR {csv_path.name}: {exc}")
                errors += 1
                continue

        total_future += report.future_removed
        total_dupes += report.duplicates_removed
        total_sorted += int(report.sort_applied)
        total_ambiguous += len(report.ambiguous_dates)

        _print_report(report, args.verbose)

    print(f"\nSummary: {len(targets) - errors} files processed, {errors} errors")
    print(f"  future rows removed : {total_future}")
    print(f"  duplicates removed  : {total_dupes}")
    print(f"  files re-sorted     : {total_sorted}")
    print(f"  ambiguous date rows : {total_ambiguous}")
    if args.dry_run:
        print("\n[DRY RUN] No files were modified.")


if __name__ == "__main__":
    main()
