---

## Objective: MarketStateEngine Legacy Feature Integration — COMPLETE

### Session 2026-05-16 (MarketStateEngine: regime, volatility_ewma, scsi):

**Three LEGACY-mined features added to MarketStateEngine (all Class B rewrites):**
- `regime: str` on `MarketState` — SPY/200-SMA binary; graceful fallback to EXPANSION + reason_code when SPY absent. Mined from `src/execution/regime_controller.py`.
- `volatility_ewma: Decimal` on `TickerFeatures` — EWMA std dev, span=38 (α=2/39). Mined from `pods/pod_core.py` EWMA_SPAN=38.
- `scsi: Decimal` on `TickerFeatures` — Stress Composite Signal Index; MVP article_count=1 formula: `(sentiment − 0.5) × ln(2)`. Mined from `src/signals/feature_engineering.py` L44-48.

**Files changed:**
- `docs/adr/0003-market-state-engine-legacy-features.md` — ADR (sealed-node gate; Status: Accepted)
- `docs/contracts/market_state_engine.md` — 3 new outputs, 4 new invariants, 2 new failure modes
- `src/portfolio_ninja/domain/objects.py` — TickerFeatures +2 fields; MarketState +regime field; validate() updated
- `src/portfolio_ninja/market_state_engine/market_state_engine.py` — 3 constants, 3 helpers, updated compute_market_state
- `tests/test_market_state_engine.py` — 2 new field assertions + 3 new tests
- `tests/test_scoring_engine.py` — 6 TickerFeatures + 3 MarketState construction sites updated
- `tests/test_domain.py` — 1 TickerFeatures factory + 5 MarketState sites updated
- `tests/test_e2e_market_state_engine.py` — 7 E2E tests (real CSV data, no mocks)
- `scripts/_sample_market_state.py` — real output verification script

**Real sample output (2026-05-16, tickers: ACN, AES, AI, window=120d):**
```
as_of_date:        2026-05-16
regime:            EXPANSION  (reason: regime_spy_missing)
params_hash:       792bac98688b7eb8e429aec13fc79e472ddd0742bf84addffb835416708217e8

Ticker       momentum_20d  volatility_20d   rsi_14   vol_ewma       scsi
------------------------------------------------------------------------
ACN        -0.1547              0.024711  33.7333   0.027990   0.244608
AES         0.0343              0.003086  69.0476   0.017954   0.209651
AI          0.0397              0.045532  48.2480   0.045739   0.235849
```

**Full test suite: 249/249 PASS, 88.96% coverage**

**Next step:** Phase 4 — ScoringEngine regime-adjusted weights (requires ADR 0004)

---

## Objective: UniverseGateway E2E Real-Data Proof — COMPLETE

### Session 2026-05-16 (UniverseGateway E2E):

**Audit finding:** Implementation was clean (no stubs/mocks). Root issue was the E2E fixture `_has_sufficient_bars()` checking total CSV line count instead of actual bars in the 120-day window. Japanese tickers (6758.T, 6861.T) had 300+ CSV rows but only 2 bars in the recent window, causing E2E pipeline failures.

**Fixes applied:**
- `tests/test_e2e_real_data.py`: replaced CSV-line-count check with `_load_csv_bars()` call (same parameters as real pipeline) — stale tickers now correctly excluded
- `tests/test_e2e_pipeline.py`: same fix; removed `_MIN_CSV_LINES` constant; added `_WINDOW_DAYS` and `_MIN_BARS_ADAPTER` for clarity

**New artifact:** `tests/test_e2e_universe_gateway.py` — 7 E2E tests using real CSV-discovered tickers:
  - `test_e2e_universe_gateway_valid_universe_from_real_tickers` — full field validation
  - `test_e2e_universe_gateway_hash_is_deterministic` — same inputs → same hash
  - `test_e2e_universe_gateway_hash_changes_with_ticker_change` — sensitivity
  - `test_e2e_universe_gateway_hash_changes_with_run_mode` — sensitivity
  - `test_e2e_universe_gateway_hash_changes_with_window` — sensitivity
  - `test_e2e_universe_gateway_downstream_dataplane_accepts_output` — no adapter hacks needed
  - `test_e2e_universe_gateway_dedup_with_real_tickers` — reason_codes populated

**Runtime evidence (2026-05-16):**
```
Discovered tickers: ['ACN', 'AES', 'AI', 'ALAB', 'AMT']
Universe: tickers=['ACN','AES','AI','ALAB','AMT'] run_mode=backtest window_days=120
         as_of_date=2026-05-16 params_hash=75a9a0a37f5456f601078ec76087eeed... validation=valid
Hash sensitivity: 4 distinct hashes for 4 distinct configs — all True
DataPlane consumed Universe directly: 5 tickers covered, validation=valid
```

**Full test suite: 239/239 PASS, 89.54% coverage**

---

## Objective: DataPlane Runtime Validation + ScoringEngine technical_composite_v1 — COMPLETE

## Status: All three phases complete. Test suite: 232/232 PASS (89.62% coverage).

## What's done (session 2026-05-16 Phase 1–3: Runtime Validation + ScoringEngine Upgrade):

### Phase 1: DataPlane E2E Real Data Validation (10/10 tests PASS)
- **Goal:** Confirm RealDataAdapter.fetch() produces valid MarketDataset from actual CSV files
- **Key issue discovered:** CSV files have varying quality; window-based filtering (120 days) reduces usable bars
  - Example: AAPL.csv has 128 CSV lines but only 29 valid bars in 120-day window (needs ≥60 minimum)
  - Solution: Added _MIN_CSV_LINES = 300 threshold to filter for complete datasets
  - Applied: _discover_tickers(n=20), _has_sufficient_bars() using line-count check
- **Tests created:** tests/test_e2e_real_data.py
  - test_e2e_real_data_market_dataset_returned — MarketDataset returned with validation_status="valid"
  - test_e2e_real_data_all_tickers_covered — every ticker in universe has data
  - test_e2e_real_data_each_ticker_has_minimum_bars — ≥21 OHLCV bars per ticker
  - test_e2e_real_data_ohlcv_fields_are_decimal — all price fields are Decimal, high≥low, close>0
  - test_e2e_real_data_params_hash_populated — SHA-256 hash present (64 hex chars)
  - test_e2e_real_data_market_state_computes_from_real_bars — MarketStateEngine produces valid state
  - test_e2e_real_data_market_state_features_are_decimal — momentum_20d, volatility_20d, rsi_14 are Decimal
  - test_e2e_real_data_market_state_features_are_nonzero — volatility > 0, rsi in [0, 100]
  - test_e2e_real_data_sentiment_is_decimal — news_sentiment is Decimal
  - test_e2e_real_data_pe_ratio_is_decimal — pe_ratio is Decimal
- **Result:** All 10 tests PASS with real CSV data from trading_data/

### Phase 2: ScoringEngine technical_composite_v1 Model (12/12 tests PASS)
- **Goal:** Replace stub_v1 random scoring with real technical-factor composite
- **ADR written:** docs/adr/0002-technical-composite-scoring.md (Status: Accepted)
- **Model formula:** score = 0.4 × norm_momentum + 0.3 × (1 − norm_volatility) + 0.3 × norm_rsi
  - Normalization: Cross-sectional min-max per run; if all values equal, return 0.5 for all tickers
  - Arithmetic: Decimal only, no float
  - Result: Clamped to [Decimal("0"), Decimal("1")]
- **Implementation:** src/portfolio_ninja/scoring_engine/scoring_engine.py
  - Added _minmax_normalize() helper for cross-sectional normalization
  - Added _technical_composite_score() for factor-based scoring
  - Updated _REGISTERED_MODELS to include "technical_composite_v1"
  - Dispatch in score_tickers() on model_id
- **Tests added:** tests/test_scoring_engine.py (4 new tests for technical_composite_v1)
  - test_scoring_engine_technical_composite_v1_returns_real_scores — verifies [0,1] range and model_id propagation
  - test_scoring_engine_technical_composite_v1_scores_differentiate_tickers — STRONG > WEAK > MID with real factors
  - test_scoring_engine_technical_composite_v1_high_momentum_scores_higher — momentum signal isolated
  - test_scoring_engine_technical_composite_v1_all_equal_features_return_half — degenerate case returns 0.5
  - Plus 8 existing stub tests (all PASS)
- **Contract updated:** docs/contracts/scoring_engine.md
  - Added technical_composite_v1 to Invariants with step-by-step algorithm
  - Documented min-max normalization and formula
  - Status: implemented
- **Result:** All 12 tests PASS; portfolio decisions now factor-driven instead of random

### Phase 3: Full E2E Pipeline with Real Data (5/5 tests PASS)
- **Goal:** Run orchestrator.run() end-to-end with RealDataAdapter + technical_composite_v1
- **Key issue:** test_e2e_pipeline.py had separate fixture with old _MIN_BARS_ADAPTER = 60 threshold
- **Fix applied:** Unified fixture filtering with Phase 1
  - Changed _MIN_CSV_LINES to 300
  - Updated _discover_tickers(n=20) and _has_sufficient_bars() threshold
  - Updated skip messages
- **Tests created:** tests/test_e2e_pipeline.py
  - test_e2e_pipeline_returns_audit_record — AuditRecord returned with validation_status="valid"
  - test_e2e_pipeline_all_hashes_populated — pipeline_hashes keys: universe, market_dataset, market_state, experiment_params, score_set, ranked_universe, target_portfolio, risk_decision, execution_intent
  - test_e2e_pipeline_operator_report_is_non_empty — render_report() produces output
  - test_e2e_pipeline_scores_differentiate_tickers — scores vary across tickers (not all equal)
  - test_e2e_pipeline_stub_model_still_works_with_real_data — regression test for stub_v1 with real data
- **Result:** All 5 tests PASS with real CSV data

### Final Coverage Report
```
Total: 232 tests PASS
Coverage: 89.62% (exceeds 80% threshold)
Key modules: scoring_engine.py 98%, orchestrator.py 100%, domain/objects.py 99%
```

## Prior work (session 2026-05-16 Phases 1–5: Module 1 Data Preparation)

Summary: DateNormalizer implementation (22 tests, 86% coverage), RealAdapter integration with force-fresh re-download, and 3 critical DataPlane fixes (CSV date parsing, NaN handling, contract status). Full suite: 213/213 PASS (89.25% coverage).

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

## Completion Status

**DataPlane Runtime Validation + ScoringEngine Upgrade: COMPLETE**
- ✓ Phase 1 E2E: 10/10 tests PASS (test_e2e_real_data.py)
- ✓ Phase 2 ScoringEngine: 12/12 tests PASS (test_scoring_engine.py: 8 stub + 4 technical_composite)
- ✓ Phase 3 Pipeline: 5/5 tests PASS (test_e2e_pipeline.py)
- ✓ Full test suite: 232/232 PASS
- ✓ Coverage: 89.62% (exceeds 80% threshold)
- ✓ ADR 0002 written (technical_composite_v1 decision)
- ✓ Contracts updated: scoring_engine.md
- ✓ No TODOs/FIXMEs in src/
- ✓ Commit message: test(e2e): unify fixture filtering in test_e2e_pipeline

**Key achievements:**
- RealDataAdapter + MarketStateEngine now runtime-validated with real CSV data
- ScoringEngine upgraded from random stub to real technical-factor composite
- All 11 pipeline modules now produce meaningful factor-driven signals
- Portfolio decisions based on (momentum, volatility, RSI) instead of random hash

**Implementation notes:**
- _MIN_CSV_LINES = 300 filters CSV files for sufficient complete bars in 120-day window
- Cross-sectional min-max normalization: (v - min) / (max - min), 0.5 when all equal
- Sealed-node architecture maintained: no cross-module contract changes
- All arithmetic Decimal-only (no float in monetary/price paths)
- Atomic writes via .tmp → os.replace() pattern

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

### Auto-snapshot: 2026-05-16T14:13:50+08:00

### Auto-snapshot: 2026-05-16T16:46:20+08:00

### Auto-snapshot: 2026-05-16T16:58:34+08:00

### Auto-snapshot: 2026-05-16T17:11:43+08:00

### Auto-snapshot: 2026-05-16T17:41:23+08:00

### Auto-snapshot: 2026-05-16T17:58:48+08:00

### Auto-snapshot: 2026-05-16T18:36:33+08:00

### Auto-snapshot: 2026-05-16T18:43:55+08:00

### Auto-snapshot: 2026-05-16T18:57:05+08:00
