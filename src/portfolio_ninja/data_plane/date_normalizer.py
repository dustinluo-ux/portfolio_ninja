"""CSV date normalization utility for dated market data files (OHLCV, fundamentals, news).

Detects date format via component sampling (first 40 rows) — if components > 12 exist,
format is unambiguous. Otherwise uses monotonic score on sample. Handles files with
fault lines (mixed formats) by detecting breaks and resolving via local window analysis.

Normalizes to ISO 8601, deduplicates, removes future rows, reconciles column schemas,
and writes atomically. Files with unresolvable fault lines are flagged for re-download
and left unchanged.
"""

from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CANDIDATE_FORMATS = {
    "-": ["%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"],
    "/": ["%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"],
}

_TITLE_TO_LOWER = {
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
    "Adj Close": "adj_close",
    "Adjusted Close": "adj_close",
}


@dataclass
class NormalizationReport:
    path: Path
    format_detected: str
    format_confidence: float
    rows_input: int
    rows_output: int
    future_removed: int
    duplicates_removed: int
    sort_applied: bool
    ambiguous_dates: list[str] = field(default_factory=list)
    needs_redownload: bool = False
    fault_lines_found: int = 0
    fault_lines_resolved: int = 0


def _try_parse(value: str, fmt: str) -> Optional[date]:
    try:
        return datetime.strptime(value.strip(), fmt).date()
    except ValueError:
        return None


def _monotonic_score(dates: list[date]) -> float:
    if len(dates) < 2:
        return 1.0
    return sum(b >= a for a, b in zip(dates, dates[1:])) / (len(dates) - 1)


def _token_exceeds_12(tokens: list[str], position: int) -> bool:
    """Check if the token at position is numeric and > 12."""
    if position >= len(tokens):
        return False
    try:
        return int(tokens[position]) > 12
    except ValueError:
        return False


def detect_date_format(date_strings: list[str], sample_size: int = 40) -> tuple[str, float]:
    """Detect date format via component sampling + monotonic score fallback.

    Algorithm:
    1. Take first sample_size rows; split by separator (-, /)
    2. If any token[0] > 12 → DD/MM/YYYY format
    3. If any token[1] > 12 → MM/DD/YYYY format
    4. If token[0] is 4-digit → YYYY-MM-DD (ISO)
    5. If all tokens ≤ 12 → compute monotonic score on sample; prefer format with
       more valid parses (tie-break)

    Returns (format_string, confidence) where confidence is 1.0 if unambiguous or
    the monotonic score on the sample if ambiguous (< 0.6 triggers redownload).
    """
    samples = [s.strip() for s in date_strings[:sample_size] if s and s.strip()]
    if not samples:
        return "%Y-%m-%d", 0.0

    sep = None
    for s in samples:
        if "-" in s:
            sep = "-"
            break
        if "/" in s:
            sep = "/"
            break
    if sep is None:
        return "%Y-%m-%d", 0.0

    candidates = _CANDIDATE_FORMATS.get(sep, ["%Y-%m-%d"])

    for s in samples:
        tokens = s.split(sep)
        if len(tokens) >= 1 and len(tokens[0]) == 4:
            try:
                int(tokens[0])
                return "%Y" + sep + "%m" + sep + "%d", 1.0
            except ValueError:
                pass
        if _token_exceeds_12(tokens, 0):
            return "%d" + sep + "%m" + sep + "%Y", 1.0
        if _token_exceeds_12(tokens, 1):
            return "%m" + sep + "%d" + sep + "%Y", 1.0

    best_fmt = candidates[0]
    best_score = -1.0
    best_count = 0

    for fmt in candidates:
        parsed = [_try_parse(s, fmt) for s in samples]
        valid = [d for d in parsed if d is not None]
        if not valid:
            continue
        score = _monotonic_score(valid)
        if score > best_score or (score == best_score and len(valid) > best_count):
            best_score = score
            best_fmt = fmt
            best_count = len(valid)

    if best_score < 0:
        return "%Y-%m-%d", 0.0

    return best_fmt, round(best_score, 4)


def _find_fault_lines(parsed_dates: list[Optional[date]]) -> list[int]:
    """Return indices where date goes backwards (parsed[i] < parsed[i-1])."""
    faults = []
    for i in range(1, len(parsed_dates)):
        if parsed_dates[i] is not None and parsed_dates[i - 1] is not None:
            if parsed_dates[i] < parsed_dates[i - 1]:
                faults.append(i)
    return faults


def _resolve_fault_region(
    rows: list[dict],
    date_col: str,
    fmt_a: str,
    fmt_b: str,
    fault_idx: int,
    window: int = 30,
) -> Optional[str]:
    """Try both formats on the ±window region around fault_idx.

    Only return a format if the ALTERNATE format (fmt_b) strictly outperforms
    the detected format (fmt_a) AND achieves score >= 0.95.
    If fmt_a is best or equal, return None (not a format-fixable fault).
    """
    start = max(0, fault_idx - window)
    end = min(len(rows), fault_idx + window)
    window_rows = rows[start:end]

    results = {}  # fmt -> (valid_count, score)

    for fmt in [fmt_a, fmt_b]:
        parsed = []
        for row in window_rows:
            raw_date = row.get(date_col, "")
            if raw_date:
                p = _try_parse(raw_date, fmt)
                if p is not None:
                    parsed.append(p)
                else:
                    parsed.append(None)
            else:
                parsed.append(None)

        valid = [d for d in parsed if d is not None]
        if not valid:
            results[fmt] = (0, 0.0)
        else:
            score = _monotonic_score(valid)
            results[fmt] = (len(valid), score)

    count_a, score_a = results[fmt_a]
    count_b, score_b = results[fmt_b]

    # If detected format already achieves high monotonicity, no format fix needed
    if score_a >= 0.95:
        return None

    # fmt_b is only resolvable if it parses more dates AND scores >= 0.95
    if count_b > count_a and score_b >= 0.95:
        return fmt_b

    return None


def _detect_date_column(fieldnames: list[str]) -> Optional[str]:
    """Return the name of the date column, or None if not found."""
    for candidate in ("date", "Date", "", None):
        if candidate in fieldnames:
            return candidate
    for name in fieldnames:
        if name and name.lower() in ("date", "datetime", "time", "timestamp"):
            return name
    return None


def _reconcile_fieldnames(fieldnames: list[str]) -> tuple[list[str], dict[str, str]]:
    """Merge Title Case and lowercase duplicate columns into a unified lowercase schema."""
    rename: dict[str, str] = {}
    seen_lower: set[str] = set()
    result: list[str] = []

    for name in fieldnames:
        lower = _TITLE_TO_LOWER.get(name, name.lower() if name else name)
        if lower in seen_lower:
            rename[name] = "__DROP__"
        else:
            seen_lower.add(lower)
            rename[name] = lower
            result.append(lower)

    return result, rename


def normalize_csv(path: Path, as_of: Optional[date] = None) -> NormalizationReport:
    """Normalize a single dated CSV file in-place.

    Pipeline:
    1. Read all rows
    2. Detect date format via sampling (component > 12 or monotonic score)
    3. Reconcile column schema (drop Title Case duplicates)
    4. Parse all dates with detected format
    5. Find fault lines (backwards jumps)
    6. For each fault: try _resolve_fault_region → re-parse bad region if resolvable
    7. If any fault unresolvable: set needs_redownload=True, return early (no write)
    8. Deduplicate (keep last), filter future, sort
    9. Atomic write
    10. Return report

    Invariant: if needs_redownload=True, file is NOT modified.
    """
    if as_of is None:
        as_of = date.today()

    if not path.exists():
        raise FileNotFoundError(f"normalize_csv: file not found: {path}")

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_fieldnames: list[str] = list(reader.fieldnames or [])
        rows: list[dict] = list(reader)

    rows_input = len(rows)

    if rows_input == 0:
        return NormalizationReport(
            path=path,
            format_detected="%Y-%m-%d",
            format_confidence=0.0,
            rows_input=0,
            rows_output=0,
            future_removed=0,
            duplicates_removed=0,
            sort_applied=False,
        )

    date_col = _detect_date_column(raw_fieldnames)
    if date_col is None:
        raise ValueError(f"normalize_csv: cannot find date column in {path}. Headers: {raw_fieldnames}")

    date_strings = [row.get(date_col, "") for row in rows]
    fmt, confidence = detect_date_format(date_strings)

    new_fieldnames, rename_map = _reconcile_fieldnames(raw_fieldnames)
    normalized_date_col = rename_map.get(date_col, date_col.lower() if date_col else "date")

    reconciled_rows: list[dict] = []
    for row in rows:
        new_row: dict = {}
        for old_key, new_key in rename_map.items():
            if new_key == "__DROP__":
                continue
            val = row.get(old_key, "")
            if new_key not in new_row or (val and not new_row[new_key]):
                new_row[new_key] = val
        reconciled_rows.append(new_row)

    parsed_dates: list[Optional[date]] = []
    for row in reconciled_rows:
        raw_date = row.get(normalized_date_col, "")
        p = _try_parse(raw_date, fmt)
        parsed_dates.append(p)

    # Check if any dates are unparseable with the detected format
    has_ambiguous = any(p is None and row.get(normalized_date_col, "").strip() for p, row in zip(parsed_dates, reconciled_rows))

    fault_lines = _find_fault_lines(parsed_dates)

    resolved = 0
    # Only attempt fault resolution if there are backward jumps AND evidence of format mixing
    # (unparseable dates). Pure ordering issues (no unparseable dates) are handled by sort+dedup.
    if fault_lines and has_ambiguous:
        logger.info("normalize_csv: %d fault line(s) found in %s", len(fault_lines), path)
        sep = "-" if "-" in fmt else "/" if "/" in fmt else "-"
        fmt_candidates = _CANDIDATE_FORMATS.get(sep, [fmt])
        fmt_other = [c for c in fmt_candidates if c != fmt][0] if len(fmt_candidates) > 1 else fmt
        for fault_idx in fault_lines:
            corrected_fmt = _resolve_fault_region(
                reconciled_rows, normalized_date_col, fmt, fmt_other, fault_idx, window=30
            )
            if corrected_fmt is None:
                logger.error(
                    "normalize_csv: unresolvable fault line at row %d in %s — marking for re-download",
                    fault_idx, path,
                )
                return NormalizationReport(
                    path=path,
                    format_detected=fmt,
                    format_confidence=confidence,
                    rows_input=rows_input,
                    rows_output=0,
                    future_removed=0,
                    duplicates_removed=0,
                    sort_applied=False,
                    needs_redownload=True,
                    fault_lines_found=len(fault_lines),
                    fault_lines_resolved=resolved,
                )

            logger.info("normalize_csv: fault at row %d resolved with format %s", fault_idx, corrected_fmt)
            start = max(0, fault_idx - 30)
            end = min(len(reconciled_rows), fault_idx + 30)
            for i in range(start, end):
                row = reconciled_rows[i]
                raw_date = row.get(normalized_date_col, "")
                if raw_date:
                    p = _try_parse(raw_date, corrected_fmt)
                    if p is not None:
                        parsed_dates[i] = p
                        row[normalized_date_col] = p.strftime("%Y-%m-%d")
            resolved += 1

    ambiguous_dates: list[str] = []
    by_date: dict[date, dict] = {}
    future_removed = 0

    for i, row in enumerate(reconciled_rows):
        parsed = parsed_dates[i]
        if parsed is None:
            raw_date = row.get(normalized_date_col, "")
            if raw_date:
                ambiguous_dates.append(raw_date)
            continue
        if parsed > as_of:
            future_removed += 1
            continue
        row[normalized_date_col] = parsed.strftime("%Y-%m-%d")
        by_date[parsed] = row

    duplicates_removed = rows_input - future_removed - len(by_date) - len(ambiguous_dates)

    sorted_dates = sorted(by_date)
    original_order = list(by_date.keys())
    sort_applied = sorted_dates != original_order

    sorted_rows = [by_date[d] for d in sorted_dates]

    if not sorted_rows:
        logger.warning("normalize_csv: no rows remain after normalization in %s", path)
        return NormalizationReport(
            path=path,
            format_detected=fmt,
            format_confidence=confidence,
            rows_input=rows_input,
            rows_output=0,
            future_removed=future_removed,
            duplicates_removed=max(0, duplicates_removed),
            sort_applied=sort_applied,
            ambiguous_dates=ambiguous_dates,
            fault_lines_found=len(fault_lines),
            fault_lines_resolved=len(fault_lines) - sum(1 for _ in fault_lines),
        )

    tmp_path = path.with_suffix(".csv.tmp")
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted_rows)

    assert os.path.getsize(tmp_path) > 0, f"normalize_csv: empty output for {path}"
    os.replace(tmp_path, path)

    return NormalizationReport(
        path=path,
        format_detected=fmt,
        format_confidence=confidence,
        rows_input=rows_input,
        rows_output=len(sorted_rows),
        future_removed=future_removed,
        duplicates_removed=max(0, duplicates_removed),
        sort_applied=sort_applied,
        ambiguous_dates=ambiguous_dates,
        fault_lines_found=len(fault_lines),
        fault_lines_resolved=resolved if fault_lines else 0,
    )


def normalize_directory(base_dir: Path, as_of: Optional[date] = None) -> list[NormalizationReport]:
    """Normalize all *.csv files found recursively under base_dir."""
    reports: list[NormalizationReport] = []
    for csv_path in sorted(base_dir.rglob("*.csv")):
        try:
            report = normalize_csv(csv_path, as_of=as_of)
            reports.append(report)
        except Exception as exc:
            logger.error("normalize_directory: failed on %s — %s", csv_path, exc)
    return reports
