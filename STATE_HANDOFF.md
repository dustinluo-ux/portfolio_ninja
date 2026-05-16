---

## Objective: Sweeping data update CLI — COMPLETE

## Status: Update script fully functional. All 3 data types (OHLCV, news, fundamentals) download correctly. Production-ready.

## What's done (session 2026-05-16 Phase 4: Sweeping Update CLI):

**Extended `scripts/update_data.py` from OHLCV-only to full sweep:**
- Loads .env automatically (EODHD_API_KEY, FMP_API_KEY)
- Batch news update: `adapter._ensure_news(tickers, date.today(), window_days=365)`
- Per-ticker fundamentals: `adapter._ensure_fundamentals(ticker)` inside loop
- Added `--skip-news` and `--skip-fundamentals` flags
- Status line shows all three data types
- Test verified: all 3 types download correctly for AAPL, MSFT, NVDA
- Production command: `conda run -n portfolio_ninja python scripts/update_data.py`

**Key design:**
- No `--force-refresh` flag needed in normal usage — staleness checks handle intelligent updates
- OHLCV: refreshes if > 1 day old
- News: refreshes if > 7 days old or missing
- Fundamentals: refreshes if missing or stale
- Graceful degradation: skips data types if API keys absent

## Prior work (session 2026-05-16 Phases 1–3):

**Phase 1: Date Normalizer Implementation (22 tests, 86% coverage)**
- Root cause: EU/US date transposition via `_parse_date()` trying `%m/%d/%Y` before `%d/%m/%Y`
- Algorithm: Component sampling (first 40 rows) + monotonic score fallback + fault-line detection
- Files created:
  - `src/portfolio_ninja/data_plane/date_normalizer.py` — 237 lines, sampling + fault-line
  - `tests/test_date_normalizer.py` — 22 tests covering format detection, normalization, fault resolution
  - `scripts/normalize_csv.py` — CLI tool with --dry-run, --verbose, --ticker, --base-dir options
  - `docs/contracts/date_normalizer.md` — contract (status: implemented)
- Verification: 109 CSV files normalized, 500 future rows removed, 0 re-download flags

**Phase 2: Real Adapter Integration (re-download trigger)**
- Added `force_fresh` parameter to `_download_ohlcv_yfinance()`
- When pre-merge normalize detects `needs_redownload=True`, recursively calls with `force_fresh=True`
- `force_fresh=True` skips merge step and overwrites CSV from scratch
- Prevents corrupted CSV data from blocking subsequent updates
- Tests: 28 real_adapter tests all pass (27 existing + 1 new re-download test)
- New test: `test_ohlcv_needs_redownload_triggers_force_fresh` — verifies force-fresh path

**Full suite verification:**
```
✓ Phase 1: test_date_normalizer.py: 22/22 PASS (86% coverage)
✓ Phase 2: test_real_adapter.py: 28/28 PASS (66% coverage of real_adapter)
✓ Full test suite: 210/210 PASS (85.09% coverage ≥ 80% threshold)
✓ Key features verified:
  - Component > 12 disambiguates format unambiguously (confidence=1.0)
  - Monotonic score resolves ambiguous dates (all ≤ 12)
  - Fault-line detection + resolution handles mixed-format CSVs
  - Unresolvable faults mark file for re-download (file not modified)
  - Force-fresh re-download overwrites corrupted CSVs cleanly
```

## Implementation Details

**date_normalizer.py pipeline:**
1. Sample first 40 rows; check if any token > 12 (unambiguous)
2. If all tokens ≤ 12, compute monotonic score on sample; tie-break by parse count
3. Parse all rows with detected format
4. Find fault lines (backwards date jumps)
5. For each fault: try alternate format on ±30 row window; only fix if alternate scores ≥ 0.95
6. If any fault unresolvable: set needs_redownload=True, return early (file unchanged)
7. Otherwise: deduplicate (keep last), filter future rows, sort, atomically write

**real_adapter integration:**
- Lines 291-301: Pre-merge normalize with needs_redownload check
- If needs_redownload=True, recursively call with force_fresh=True
- Lines 325-330: force_fresh=True skips merge (existing = None)
- Lines 345-349: Post-save normalize for sort/dedup/future-row cleanup

## Next Steps

Phase 3 (deferred): Extend pattern to fundamentals and news download functions.
- Same needs_redownload trigger logic applies generically to any dated CSV
- _download_news_sentiment_eodhd() and _download_fundamentals_fmp() can use same pattern

## Notes:
- date_normalizer.py: stdlib csv only, no pandas (matches _load_csv_bars pattern)
- Monotonic scoring: (count of non-decreasing pairs) / (total pairs - 1)
- Confidence < 0.6 → logs warning, defaults to ISO
- Atomic write: .tmp file → validate non-empty → os.replace()
- Use conda env "portfolio_ninja"

### Auto-snapshot: 2026-05-16

### Auto-snapshot: 2026-05-16T11:13:04+08:00

### Auto-snapshot: 2026-05-16T11:35:43+08:00

### Auto-snapshot: 2026-05-16T11:46:12+08:00

### Auto-snapshot: 2026-05-16T11:52:35+08:00

### Auto-snapshot: 2026-05-16T11:58:53+08:00

### Auto-snapshot: 2026-05-16T12:09:52+08:00

### Auto-snapshot: 2026-05-16T12:15:28+08:00

### Auto-snapshot: 2026-05-16T12:31:08+08:00

### Auto-snapshot: 2026-05-16T12:46:53+08:00

### Auto-snapshot: 2026-05-16T13:22:11+08:00
