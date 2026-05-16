# Contract: DateNormalizer

## Purpose
Detects date format ambiguity in OHLCV CSV files using sequential (monotonic) validation and normalizes all dates to ISO 8601, deduplicates, removes future-dated rows, reconciles column schemas, and sorts chronologically — ensuring every CSV is clean before and after a merge operation.

## Status
approved

## Inputs

| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| path | Path | caller | yes | Path to the CSV file to normalize |
| as_of | date | caller | no | Upper date bound; rows after this date are removed. Defaults to `date.today()` |

## Outputs

| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| NormalizationReport | dataclass | caller / CLI logger | Summary of actions taken on the file |

### NormalizationReport fields

| Field | Type | Description |
|-------|------|-------------|
| path | Path | Absolute path of the file processed |
| format_detected | str | Format string that won the monotonic test (e.g. `%Y-%m-%d`) |
| format_confidence | float | Monotonic score of the winning format (0.0–1.0) |
| rows_input | int | Row count before normalization |
| rows_output | int | Row count after normalization |
| future_removed | int | Rows dropped because bar_date > as_of |
| duplicates_removed | int | Rows dropped because of duplicate normalized date |
| sort_applied | bool | True if rows were reordered |
| ambiguous_dates | list[str] | Raw date strings that could not be assigned to a format with confidence ≥ 0.6 |

## Dependencies
- stdlib only (`csv`, `datetime`, `os`, `pathlib`) — no pandas, no third-party imports

## Invariants
- All dates in the output CSV are ISO 8601 (`YYYY-MM-DD`)
- Output rows are sorted ascending by date
- No row with `bar_date > as_of` survives normalization
- Write is atomic: `.csv.tmp` → validate non-empty → `os.replace()` to target
- Monetary values are untouched (pass-through strings; no float conversion)
- The function is idempotent: running it twice on the same file produces identical output
- If `format_confidence < 0.6`, the function logs a warning and defaults to ISO without crashing

## Failure Modes

| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|-----------|
| Ambiguous date format (all values ≤ 12, any format gives same order) | M | M | Log warning; emit low-confidence report; default to ISO and continue |
| CSV with no parseable dates at all | L | H | Raise `ValueError` with path; caller decides to skip or abort |
| Empty CSV file | L | L | Return report with `rows_input=0`, skip write |
| Write permission denied | L | H | Propagate `OSError`; tmp file cleaned up by caller |
| Mixed formats within one file | L | H | Winning format applied to all rows; rows that fail to parse under winning format are dropped and logged |

## Tests Required
- [ ] `test_detect_iso_monotonic` — ISO file → `(%Y-%m-%d, 1.0)`
- [ ] `test_detect_eu_by_sequence` — EU dates all ≤ 12 → `(%d/%m/%Y, 1.0)` via sequence
- [ ] `test_detect_us_by_sequence` — US dates all ≤ 12 → `(%m/%d/%Y, 1.0)` via sequence
- [ ] `test_ambiguous_low_confidence` — any format gives same order → confidence < 0.6
- [ ] `test_normalize_fixes_transposition` — EU date in file → normalized to correct ISO date
- [ ] `test_normalize_removes_future_rows` — rows with date > as_of removed
- [ ] `test_normalize_sorts_ascending` — out-of-order rows sorted
- [ ] `test_normalize_deduplicates_keep_last` — duplicate date rows → keep last
- [ ] `test_normalize_reconciles_columns` — dual-schema header → unified lowercase
- [ ] `test_normalize_atomic_write_cleans_tmp` — no `.tmp` file left after success
- [ ] `test_normalize_empty_date_skipped` — row with blank date skipped without crash
- [ ] `test_monotonic_score_with_gaps` — weekend/holiday gaps score near 1.0

## Acceptance Criteria
- [ ] `detect_date_format` correctly identifies EU vs US vs ISO via monotonic scoring
- [ ] `normalize_csv` produces idempotent ISO output
- [ ] `normalize_directory` processes all `*.csv` files under a directory tree
- [ ] All 12 tests pass
- [ ] Integration: `_download_ohlcv_yfinance` calls `normalize_csv` before reading existing and after saving

## Upstream Providers
- Caller (real_adapter.py download functions, normalize_csv.py CLI)

## Downstream Consumers
- `real_adapter._download_ohlcv_yfinance` (gated by normalized CSV before merge)
- `scripts/normalize_csv.py` (CLI cleanup of existing files)
