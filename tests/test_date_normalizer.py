"""Tests for date_normalizer — sequential (monotonic) format detection and normalization."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from portfolio_ninja.data_plane.date_normalizer import (
    detect_date_format,
    normalize_csv,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# detect_date_format — sequential / monotonic scoring
# ---------------------------------------------------------------------------

class TestDetectDateFormat:
    def test_detect_iso_monotonic(self):
        dates = ["2026-01-02", "2026-01-05", "2026-01-07", "2026-02-03"]
        fmt, confidence = detect_date_format(dates)
        assert fmt == "%Y-%m-%d"
        assert confidence == pytest.approx(1.0)

    def test_detect_eu_by_sequence(self):
        # Dates in order: 1 Jan, 2 Jan, 3 Jan, 4 Jan (all day ≤ 12)
        # EU format (DD/MM/YYYY): 01/01/26, 02/01/26 ... stays ordered
        # US format (MM/DD/YYYY): would parse as Jan1, Jan2, Jan3, Jan4 — same order!
        # Need day > 12 OR a sequence that breaks under one format
        # Use: 13/01/2026, 14/01/2026, 15/01/2026
        dates = ["13/01/2026", "14/01/2026", "15/01/2026", "16/01/2026"]
        fmt, confidence = detect_date_format(dates)
        assert fmt == "%d/%m/%Y"
        assert confidence == pytest.approx(1.0)

    def test_detect_us_by_sequence(self):
        # Months > 12 in second position would indicate US format
        # Use: 01/13/2026, 01/14/2026 (Jan 13, Jan 14 US; but 13th month is invalid EU)
        dates = ["01/13/2026", "01/14/2026", "01/15/2026"]
        fmt, confidence = detect_date_format(dates)
        assert fmt == "%m/%d/%Y"
        assert confidence == pytest.approx(1.0)

    def test_detect_eu_vs_us_via_monotonic_ambiguous_values(self):
        # Dates: 03/04/2026, 06/04/2026, 09/04/2026 — all ≤ 12 in both positions
        # EU parse: Mar4, Jun4, Sep4 → monotonic (score=1.0)
        # US parse: Apr3, Apr6, Apr9 → monotonic (score=1.0) — tie, goes to first candidate
        # With same score the function returns the first candidate; both are valid orderings
        dates = ["03/04/2026", "06/04/2026", "09/04/2026"]
        fmt, confidence = detect_date_format(dates)
        # Any format that scores 1.0 is acceptable here; just check confidence is high
        assert confidence == pytest.approx(1.0)

    def test_ambiguous_low_confidence_when_all_formats_fail(self):
        # Non-parseable values → 0 confidence
        dates = ["not-a-date", "also-not", "nope"]
        fmt, confidence = detect_date_format(dates)
        assert fmt == "%Y-%m-%d"
        assert confidence == pytest.approx(0.0)

    def test_empty_list(self):
        fmt, confidence = detect_date_format([])
        assert fmt == "%Y-%m-%d"
        assert confidence == pytest.approx(0.0)

    def test_monotonic_score_with_weekend_gaps(self):
        # Trading data skips weekends — large forward gaps are still monotonic
        dates = [
            "2026-01-02", "2026-01-05",  # Fri→Mon gap
            "2026-01-06", "2026-01-07",
            "2026-01-08", "2026-01-09",
            "2026-01-12",  # Mon after weekend
        ]
        fmt, confidence = detect_date_format(dates)
        assert fmt == "%Y-%m-%d"
        assert confidence == pytest.approx(1.0)

    def test_detect_by_component_exceeds_12_position_0(self):
        # Token[0] > 12 → unambiguously DD/MM/YYYY
        dates = ["13/01/2026", "14/01/2026", "15/01/2026"]
        fmt, confidence = detect_date_format(dates)
        assert fmt == "%d/%m/%Y"
        assert confidence == 1.0

    def test_detect_us_by_component_exceeds_12_position_1(self):
        # Token[1] > 12 → unambiguously MM/DD/YYYY
        dates = ["01/13/2026", "01/14/2026", "01/15/2026"]
        fmt, confidence = detect_date_format(dates)
        assert fmt == "%m/%d/%Y"
        assert confidence == 1.0


# ---------------------------------------------------------------------------
# normalize_csv — end-to-end
# ---------------------------------------------------------------------------

class TestNormalizeCsv:
    def test_normalize_fixes_transposition(self, tmp_path):
        # EU date 04/03/2026 = March 4; if mis-parsed as US = April 3
        # File order: Jan→Feb→Mar → under EU parse stays monotonic
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "14/01/2026", "open": "100", "close": "101"},
            {"date": "15/01/2026", "open": "102", "close": "103"},
            {"date": "04/03/2026", "open": "110", "close": "111"},  # March 4 EU
        ]
        _write_csv(csv_file, ["date", "open", "close"], rows)

        report = normalize_csv(csv_file, as_of=date(2026, 12, 31))

        result = _read_csv(csv_file)
        dates = [r["date"] for r in result]
        assert "2026-01-14" in dates
        assert "2026-03-04" in dates
        # Must not contain the US-misparse date
        assert "2026-04-03" not in dates
        assert report.format_detected == "%d/%m/%Y"
        assert report.format_confidence == pytest.approx(1.0)

    def test_normalize_removes_future_rows(self, tmp_path):
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "2026-01-02", "close": "100"},
            {"date": "2027-06-01", "close": "999"},  # future
        ]
        _write_csv(csv_file, ["date", "close"], rows)

        report = normalize_csv(csv_file, as_of=date(2026, 5, 16))

        result = _read_csv(csv_file)
        assert len(result) == 1
        assert result[0]["date"] == "2026-01-02"
        assert report.future_removed == 1
        assert report.rows_output == 1

    def test_normalize_sorts_ascending(self, tmp_path):
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "2026-03-01", "close": "300"},
            {"date": "2026-01-01", "close": "100"},
            {"date": "2026-02-01", "close": "200"},
        ]
        _write_csv(csv_file, ["date", "close"], rows)

        report = normalize_csv(csv_file, as_of=date(2026, 12, 31))

        result = _read_csv(csv_file)
        dates = [r["date"] for r in result]
        assert dates == sorted(dates)
        assert report.sort_applied is True

    def test_normalize_deduplicates_keep_last(self, tmp_path):
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "2026-01-02", "close": "100"},
            {"date": "2026-01-02", "close": "200"},  # duplicate date, keep this
            {"date": "2026-01-03", "close": "150"},
        ]
        _write_csv(csv_file, ["date", "close"], rows)

        report = normalize_csv(csv_file, as_of=date(2026, 12, 31))

        result = _read_csv(csv_file)
        jan2_rows = [r for r in result if r["date"] == "2026-01-02"]
        assert len(jan2_rows) == 1
        assert jan2_rows[0]["close"] == "200"  # kept last
        assert report.duplicates_removed == 1
        assert report.rows_output == 2

    def test_normalize_reconciles_columns(self, tmp_path):
        # Dual-schema header: lowercase + Title Case duplicates
        csv_file = tmp_path / "TEST.csv"
        headers = ["date", "open", "close", "Date", "Open", "Close"]
        rows = [
            {"date": "2026-01-02", "open": "100", "close": "101", "Date": "", "Open": "", "Close": ""},
        ]
        _write_csv(csv_file, headers, rows)

        normalize_csv(csv_file, as_of=date(2026, 12, 31))

        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            out_headers = list(reader.fieldnames or [])

        # Title Case duplicates should be removed
        assert "Date" not in out_headers
        assert "Open" not in out_headers
        assert "Close" not in out_headers
        assert "date" in out_headers

    def test_normalize_atomic_write_cleans_tmp(self, tmp_path):
        csv_file = tmp_path / "TEST.csv"
        rows = [{"date": "2026-01-02", "close": "100"}]
        _write_csv(csv_file, ["date", "close"], rows)

        normalize_csv(csv_file, as_of=date(2026, 12, 31))

        tmp_file = csv_file.with_suffix(".csv.tmp")
        assert not tmp_file.exists()

    def test_normalize_empty_date_skipped(self, tmp_path):
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "", "close": "999"},         # empty date → skip
            {"date": "2026-01-02", "close": "100"},
        ]
        _write_csv(csv_file, ["date", "close"], rows)

        report = normalize_csv(csv_file, as_of=date(2026, 12, 31))

        result = _read_csv(csv_file)
        assert len(result) == 1
        assert result[0]["date"] == "2026-01-02"
        assert report.rows_output == 1

    def test_normalize_idempotent(self, tmp_path):
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "2026-01-02", "close": "100"},
            {"date": "2026-01-05", "close": "105"},
        ]
        _write_csv(csv_file, ["date", "close"], rows)

        report1 = normalize_csv(csv_file, as_of=date(2026, 12, 31))
        report2 = normalize_csv(csv_file, as_of=date(2026, 12, 31))

        assert report1.rows_output == report2.rows_output
        assert not report2.sort_applied
        assert report2.duplicates_removed == 0
        assert report2.future_removed == 0

    def test_normalize_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            normalize_csv(tmp_path / "missing.csv")

    def test_normalize_all_future_rows_warns_empty(self, tmp_path):
        csv_file = tmp_path / "TEST.csv"
        rows = [{"date": "2030-01-01", "close": "999"}]
        _write_csv(csv_file, ["date", "close"], rows)

        report = normalize_csv(csv_file, as_of=date(2026, 5, 16))

        assert report.rows_output == 0
        assert report.future_removed == 1

    def test_fault_line_single_region_fixed(self, tmp_path):
        # File has a fault line: EU dates, then US format in middle region, then back to EU
        # The fault should be detected and local window analysis should fix it
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "01/01/2026", "close": "100"},  # Jan 1 (EU or US, same)
            {"date": "02/01/2026", "close": "101"},  # Feb 1 (EU) or Jan 2 (US)
            {"date": "03/01/2026", "close": "102"},  # Mar 1 (EU) or Jan 3 (US)
            {"date": "01/04/2026", "close": "103"},  # FAULT: Jan 4 (US) < Mar 1 (EU) → backwards
            {"date": "02/04/2026", "close": "104"},  # Jan 5 (US) or Feb 4 (EU)
            {"date": "04/04/2026", "close": "105"},  # Jan 6 (US) or Apr 4 (EU)
            {"date": "05/05/2026", "close": "106"},  # May 5 (both)
        ]
        _write_csv(csv_file, ["date", "close"], rows)

        report = normalize_csv(csv_file, as_of=date(2026, 12, 31))

        # File should be successfully processed (not marked for redownload)
        assert report.needs_redownload is False
        result = _read_csv(csv_file)
        dates = [r["date"] for r in result]
        # All dates should be parseable and in order
        assert len(dates) > 0
        assert dates == sorted(dates)

    def test_fault_line_unresolvable_sets_flag(self, tmp_path):
        # File with mixed formats where fault can't be resolved
        # Start with unambiguous MM/DD (13 > 12 in position 1), then a date that fails MM/DD
        # and a backwards valid date — fault resolution fails because alternate format parses fewer dates
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "01/13/2026", "close": "100"},   # Jan 13, 2026 (13 > 12 → MM/DD unambiguous)
            {"date": "02/14/2026", "close": "101"},   # Feb 14, 2026 MM/DD
            {"date": "12/01/2025", "close": "102"},   # Dec 1, 2025 MM/DD (backwards from Feb 14)
            {"date": "25/12/2025", "close": "999"},   # Fails MM/DD (25 > 12 month), would be Dec 25 EU
        ]
        _write_csv(csv_file, ["date", "close"], rows)

        report = normalize_csv(csv_file, as_of=date(2026, 12, 31))

        # Should mark for re-download, leave file unchanged
        assert report.needs_redownload is True
        result = _read_csv(csv_file)
        # File should be unchanged (dates not normalized)
        assert len(result) == len(rows)
        assert result[0]["date"] == "01/13/2026"  # unchanged
        assert result[3]["date"] == "25/12/2025"  # unchanged

    def test_normalize_file_unchanged_on_redownload_flag(self, tmp_path):
        # When needs_redownload=True, the file bytes should be identical
        # Use mixed formats with unparseable dates to trigger has_ambiguous=True
        csv_file = tmp_path / "TEST.csv"
        rows = [
            {"date": "01/13/2026", "close": "100"},   # Jan 13, 2026 (unambiguous MM/DD)
            {"date": "02/14/2026", "close": "101"},   # Feb 14, 2026
            {"date": "12/01/2025", "close": "102"},   # Dec 1, 2025 (backwards)
            {"date": "25/12/2025", "close": "999"},   # Fails MM/DD, triggers has_ambiguous
        ]
        _write_csv(csv_file, ["date", "close"], rows)

        original_bytes = csv_file.read_bytes()
        report = normalize_csv(csv_file, as_of=date(2026, 12, 31))
        result_bytes = csv_file.read_bytes()

        assert report.needs_redownload is True
        assert original_bytes == result_bytes
