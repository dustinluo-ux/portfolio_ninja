# LEGACY_MINING_EVIDENCE.md
# Reuse Candidates — Evidence-Backed Detail
> Generated: 2026-05-13 | Every claim backed by file + line range.
> No line evidence = no direct reuse claim.

---

## Candidate 1: TDO Validation System

**File:** `tdo_validator.py`
**Lines:** 1–469
**Target Module:** AuditMonitor

### Functions/Classes
- `compute_audit_hash(auditor_section: dict) → str` — SHA-256 of canonical JSON payload. Prefix `"audit_"`. Returns hex string.
- `verify_audit_hash(auditor_section: dict) → bool` — re-derives and compares. Never raises.
- `validate_tdo(tdo, expected_phase, now_utc) → ValidationResult` — JSON Schema + 9 Red Team Constraints.
- `validate_tdo_or_raise(tdo, expected_phase, now_utc)` — raises `AuditConstraintError` on failure.
- `AuditConstraintError(ValueError)` — structured with `code` and `message` fields.

### Inputs
- `tdo: dict` — raw TDO JSON object (conforming to THESIS_SCHEMA.json v1.0.0)
- `expected_phase: str` — e.g., `"SCOUTED"`, `"AUDITED"`, `"PROMOTED"`
- `now_utc: datetime` — caller-injected timestamp (deterministic, testable)

### Outputs
- `ValidationResult` — named tuple `(passed: bool, errors: list[str])`
- `AuditConstraintError` — raised on hard violations

### Side Effects
- None — purely in-memory

### Dependencies
- `jsonschema` — schema validation
- `THESIS_SCHEMA.json` — loaded at import time from adjacent path

### Constants (lines ~15-25)
```python
MARKET_CAP_CEILING_USD = 50_000_000_000
MIN_SUPPORTING_FINDINGS = 3
MIN_COMPOSITE_SCORE = 0.30
MAX_THESIS_AGE_DAYS = 90
SAME_DAY_EXECUTION_GATE_HOURS = 24
```

### Tests Found
- `tests/test_tdo_validator.py` — full Red Team Constraint coverage (comprehensive)

### Coupling Risk
- LOW — only depends on `jsonschema` and adjacent JSON schema file

### Reuse Verdict
**A — Direct reuse.** `compute_audit_hash()` maps directly to `params_hash` derivation in AuditRecord. `validate_tdo_or_raise()` is the right pattern. Port both. Update `THESIS_SCHEMA.json` path to be relative, not hardcoded.

---

## Candidate 2: Execution Eligibility Gate

**File:** `auditor/tdo_gate.py`
**Lines:** 1–239
**Target Module:** AuditMonitor (gate); RiskEngine (kill_switch check)

### Functions/Classes
- `verify_execution_eligibility(tdo, *, now_utc, available_funds) → bool` — 7-check gate:
  1. Phase check (`phase == "PROMOTED"`)
  2. Audit hash verification (`verify_audit_hash()`)
  3. Cap rule passed (`cap_rule_passed == true`)
  4. 24h contamination gate from `created_at`
  5. Market cap < $50B
  6. Thesis age < 90 days from `audited_at`
  7. Kill switch (`kill_switch_active == false`)

### Inputs
- `tdo: dict`
- `now_utc: datetime`
- `available_funds: float | None` (not yet used in validation logic — future hook)

### Outputs
- `bool` — True = eligible, False = blocked (with logging)

### Side Effects
- Logs to `logging` (no file writes)

### Tests Found
- `tests/test_tdo_gate.py` — 10 scenarios including each check failing independently

### Coupling Risk
- LOW — calls `verify_audit_hash()` from `tdo_validator.py` only

### Reuse Verdict
**A — Direct reuse.** Kill_switch check (#7) belongs in RiskEngine as a hard block. All other checks belong in AuditMonitor. Split cleanly at kill_switch.

---

## Candidate 3: PipelineState + VendorEvent

**File:** `src/core/state.py`
**Lines:** 1–114
**Target Module:** AuditMonitor (lineage tracking), DataPlane (vendor events)

### Classes
- `VendorEvent` (dataclass): `source: str`, `event_type: str`, `latency_ms: float`, `ticker: str | None`, `detail: str | None`
- `PipelineState` (dataclass): `as_of`, `vendor_events: list[VendorEvent]`, `orders`, `warnings`, `fallback_counts: dict[str, int]`, `metadata: dict`
  - `add_vendor_event(event: VendorEvent)`
  - `fallback_count(source: str) → int`
  - `to_dict() → dict`
  - `save(path: Path)` — atomic write (`.tmp` → `os.replace()`)

### Side Effects
- `save()` writes to disk — atomic pattern

### Dependencies
- `pathlib`, `json`, `os` — stdlib only

### Tests Found
- None found in scanned test files — test gap

### Coupling Risk
- LOW — standalone dataclass, no external deps

### Reuse Verdict
**A — Direct reuse.** `VendorEvent` maps to DataPlane telemetry. `PipelineState.save()` shows the atomic write pattern already in place. `fallback_count()` is directly useful for DataQualityReport. Port to `domain/objects.py` or `domain/stubs.py` as pipeline telemetry.

---

## Candidate 4: Resilience Layer (Data Fallback Chain)

**File:** `src/data/resilience_layer.py`
**Lines:** 1–254
**Target Module:** DataPlane (StubDataAdapter → real adapter replacement)

### Functions
- `get_prices(tickers, start, end, data_dir, *, marketaux_api_key, state) → dict[str, DataFrame]`
  - Tries: CSV → Marketaux → YFinance
  - Minimum 5 rows per ticker
  - Logs `VendorEvent` for each vendor attempt
  - Calls `_cast_ohlc_to_decimal()` on success
  - Failed tickers: omitted from result (no raise)
- `_cast_ohlc_to_decimal(df) → df`: converts `open/high/low/close` columns from float to Decimal
- `_try_marketaux(...)` — bare `except Exception: return None`
- `_try_yfinance(...)` — bare `except Exception: return None`

### Inputs
- `tickers: list[str]`
- `start, end: date`
- `data_dir: Path`
- `marketaux_api_key: str | None`
- `state: PipelineState` (for vendor event logging)

### Outputs
- `dict[str, DataFrame]` — OHLCV per ticker with Decimal OHLC columns

### Side Effects
- Mutates `state.vendor_events` (appends events)
- Makes network calls (Marketaux, YFinance) if CSV fails

### Dependencies
- `pandas`, `decimal`
- `marketaux` (optional external API)
- `yfinance` (optional fallback)
- `src.core.state.PipelineState`

### Tests Found
- None found — test gap (critical)

### Coupling Risk
- LOW for internal logic; MEDIUM for external vendor calls

### Reuse Verdict
**A — Direct reuse for `_cast_ohlc_to_decimal()` and fallback pattern.** The CSV→Marketaux→YFinance chain is the production data path. `_try_marketaux` and `_try_yfinance` must have bare excepts replaced with explicit `VendorEvent(event_type="FAILURE")` logging + structured return. This is the real `DataAdapter` implementation for non-MVP builds.

---

## Candidate 5: DataQualityReport

**File:** `src/data/data_quality.py`
**Lines:** 1–46
**Target Module:** DataPlane

### Classes
- `DataQualityReport` (dataclass): `critical_missing: list[str]`, `degraded_missing: list[str]`, `warnings: list[str]`, `can_rebalance: bool`
- `IncompleteDataError(Exception)` — raised when critical sources missing

### Constants
```python
CRITICAL_SOURCES = ["prices", "smh_benchmark", "regime_status"]
DEGRADED_SOURCES = ["eodhd_news", "tiingo_news", "marketaux_news", "meta_weights"]
```

### Side Effects
- None — pure data class + constants

### Coupling Risk
- LOW

### Reuse Verdict
**A — Direct reuse.** `DataQualityReport` pattern maps to DataPlane output invariant. `IncompleteDataError` maps to `DataPlane → MarketDataset` validation failure path. Port to `domain/objects.py`. Adapt `CRITICAL_SOURCES` to match new architecture's data sources.

---

## Candidate 6: ExecutionPlanner

**File:** `src/execution/planner.py`
**Lines:** 1–219
**Target Module:** ExecutionEngine

### Class: `ExecutionPlanner`
- `reconcile(target: TargetPortfolio, constraints: RiskConstraints, nav: Decimal, nq_price: Decimal, prices_dict, spy_series) → FinalExecutionPlan`
  - Stop-loss check: if `stop_loss_active → zero all weights`
  - Scale: `long_orders[t] = weights[t] × position_scale`
  - Beta gap: if `portfolio_beta - beta_cap > BETA_GAP_THRESHOLD(0.05)` → add MNQ short overlay
  - Options: if `options_hedge_enabled` → add SMH put order via `estimate_smh_put_cost()`
- `_compute_portfolio_beta(weights, prices_dict, spy_series) → Decimal`
  - 60-day OLS per ticker vs SPY
  - Clamps to [0, 3]
  - Weighted sum for portfolio beta

### Constants
```python
BETA_GAP_THRESHOLD = Decimal("0.05")
MNQ_MULTIPLIER = Decimal("2")
MES_MULTIPLIER = Decimal("5")
```

### All Monetary Fields
- `nav: Decimal`, `nq_price: Decimal`, `long_orders: dict[str, Decimal]`
- `OverlayOrder.quantity: Decimal`
- `OptionOrder.strike: Decimal`, `premium_estimate: Decimal`
- **Decimal-clean throughout**

### Tests Found
- None found in test scan — test gap

### Coupling Risk
- MEDIUM — depends on `TargetPortfolio`, `RiskConstraints`, `FinalExecutionPlan` from `src/risk/types.py`

### Reuse Verdict
**A — Direct reuse for stop-loss zeroing, beta computation, and order scaling.** MNQ/SMH overlay is future scope — exclude from MVP ExecutionEngine. `_compute_portfolio_beta()` is clean Decimal OLS, directly portable.

---

## Candidate 7: Risk Domain Types

**File:** `src/risk/types.py`
**Lines:** 1–69
**Target Module:** RiskEngine, ExecutionEngine

### Classes (all frozen dataclasses)
```python
TargetPortfolio:
    as_of: pd.Timestamp
    weights: dict[str, Decimal]   # Decimal-clean
    scores: dict[str, float]      # float — port as Decimal
    construction_meta: dict

RiskConstraints:
    as_of: pd.Timestamp
    beta_cap: Decimal
    position_scale: Decimal
    stop_loss_active: bool
    margin_headroom_pct: Decimal
    audit_log: tuple[str, ...]    # immutable audit trail

FinalExecutionPlan:
    as_of: pd.Timestamp
    long_orders: dict[str, Decimal]
    overlay_orders: list[OverlayOrder]
    option_orders: list[OptionOrder]
    audit_trail: tuple[str, ...]

OverlayOrder:
    instrument: str
    quantity: Decimal
    direction: str

OptionOrder:
    underlying: str
    option_type: str
    strike: Decimal
    expiry: date
    quantity: int
    premium_estimate: Decimal
```

### Side Effects
- None — pure frozen dataclasses

### Coupling Risk
- HIGH — cross-referenced by planner.py and execution pipeline

### Reuse Verdict
**A — Direct template for new domain objects.** Port `TargetPortfolio.weights` and `RiskConstraints` fields to new domain. Change `scores: dict[str, float]` to `dict[str, Decimal]`. `FinalExecutionPlan` is the template for `ExecutionIntent` with typed order list.

---

## Candidate 8: TES Scorer

**File:** `lib/shared_core/tes_scorer.py`
**Lines:** 1–110
**Target Module:** ScoringEngine

### Functions
- `calculate_tes_score(revenue_ratio, divisional_cagr, patent_density) → float`
  - Formula: `TES = revenue_ratio × (1 + divisional_cagr) × patent_density`
  - Decimal used internally for computation
  - Clamps to [0, 1_000_000]
  - Returns `float` — contamination
- `estimate_patent_density(ticker, config) → float`
  - Always returns `config.get("patent_density_default", 0.10)`
  - USPTO not integrated — constant stub
- `build_tes_components(auditor, config) → dict`
  - Merges confidence: STUB/ESTIMATED/COMPUTED per field

### Inputs
- `revenue_ratio: float` — niche_revenue / total_revenue
- `divisional_cagr: float` — divisional revenue growth rate
- `patent_density: float` — always 0.10 in practice

### Outputs
- `float` — contaminated at output boundary

### Side Effects
- None

### Dependencies
- `decimal.Decimal` — used internally
- No external imports

### Tests Found
- None found in test scan

### Coupling Risk
- LOW

### Reuse Verdict
**C — Rewrite.** Formula idea is sound. Must: (1) return `Decimal` not `float`, (2) document patent_density as `Decimal("0.10")` constant with `reason_codes = ["patent_density_stub"]`, (3) accept `Decimal` inputs. The formula `revenue_ratio × (1+cagr) × patent_density` is the TES signal for ScoringEngine.

---

## Candidate 9: Model Factory

**File:** `src/models/model_factory.py`
**Lines:** 1–69
**Target Module:** ExperimentEngine

### Registry
```python
MODEL_REGISTRY = {
    "linear": LinearReturnPredictor,
    "ridge": RidgeReturnPredictor,
    "lasso": LassoReturnPredictor,
    "xgboost": XGBoostReturnPredictor,
    "catboost": CatBoostReturnPredictor,
}
```

### Functions
- `create_model(model_config: dict, feature_names: list[str]) → BaseReturnPredictor`
- `list_available_models() → list[str]`
- `get_best_model(model_dir: Path) → BaseReturnPredictor` — reads IC from YAML, selects highest

### Live Model
- `models/saved/catboost_20260308_103404.pkl` — loadable, trained 2026-03-08

### Tests Found
- Multiple `tests/tmp/test_get_best_model_*` directories with `model_config.yaml` fixtures

### Coupling Risk
- LOW — registry pattern with clean interface

### Reuse Verdict
**A — Direct reuse.** Registry pattern maps to ExperimentEngine's model selection. `get_best_model()` is the right interface for dynamic model selection. Port `BaseReturnPredictor` interface to new domain.

---

## Candidate 10: Regime Controller

**File:** `src/execution/regime_controller.py`
**Lines:** 1–70
**Target Module:** MarketStateEngine (regime feature), RiskEngine (constraint adjustment)

### Functions
- `RegimeController.compute(as_of_date) → dict`
  - Reads `regime_status.json` (written by watcher)
  - BEAR → Contraction: `{multiplier: 0.6, score_floor: 0.65, max_longs: 3, n_shorts: 3}`
  - else → Expansion: `{multiplier: 1.0, score_floor: 0.50, max_longs: 5, n_shorts: 0}`
- `write_regime_status(status: dict, path: Path)` — atomic JSON write

### Inputs
- `as_of_date: date`

### Outputs
- `dict` — regime classification with multiplier, score_floor, max_longs, n_shorts

### Side Effects
- `compute()` reads `regime_status.json` from disk
- `write_regime_status()` writes to disk — atomic

### Coupling Risk
- LOW — reads/writes one JSON file

### Reuse Verdict
**B — Idea reuse.** Regime classification (BEAR/BULL binary) maps to a `regime: str` field on `MarketState`. The constraint parameters (multiplier, score_floor, max_longs) map to `ExperimentParams` overrides injected by `ExperimentEngine`. Atomic write pattern is correct.

---

## Candidate 11: Incident Logger

**File:** `src/monitoring/incident_logger.py`
**Lines:** 1–35
**Target Module:** AuditMonitor

### Functions
- `log_incident(event_type: str, payload: dict, log_path: Path)` — appends JSONL. Never raises.

### Inputs
- `event_type: str` — incident category
- `payload: dict` — arbitrary incident data
- `log_path: Path` — target JSONL file

### Outputs
- None — side effect only

### Side Effects
- Appends one line to JSONL file

### Dependencies
- `json`, `pathlib` — stdlib only

### Tests Found
- None

### Coupling Risk
- LOW

### Reuse Verdict
**A — Direct reuse.** Append-only JSONL is the correct AuditRecord persistence pattern. Port verbatim. AuditMonitor uses this to write `AuditRecord` entries.

---

## Candidate 12: Skeptic Gate Thresholds

**File:** `src/agents/skeptic_gate.py`
**Lines:** 1–146
**Target Module:** ScoreArbitrationEngine

### Constants (lines 75-84)
```python
WEIGHT_TRIGGER = Decimal("0.15")
# Flags:
PE > 35       → VALUATION_PE
PB > 5        → VALUATION_PB
D/E > 2       → DISTRESSED_DEBT
current_ratio < 1  → DISTRESSED_LIQUIDITY
52w_drawdown < -40% → DISTRESSED_DRAWDOWN
# FAIL if: weight > 15% AND flags >= 2 AND at least 1 distress flag
```

### Functions
- `run_gate(weights, ticker_list) → GateResult` — FAIL/PASS/SKIP
- `fetch_bear_fundamentals(ticker) → BearFindings` — yfinance fetch, never raises
- `_audit_bear(findings) → BearFindings` — applies thresholds

### Side Effects
- External network call (yfinance) in `fetch_bear_fundamentals()`
- SKIP returned on any exception

### Coupling Risk
- LOW for gate logic itself; MEDIUM for yfinance dependency

### Reuse Verdict
**B — Idea reuse.** Threshold values and gate logic are the valuable part. Rewrite to use `MarketState` fields instead of yfinance fetch. SKIP-on-exception must become structured error. Port as a filter step in `ScoreArbitrationEngine` after ranking.

---

## Candidate 13: SCSI Formula

**File:** `src/signals/feature_engineering.py`
**Lines:** 44–70
**Target Module:** MarketStateEngine

### Formula
```python
# Per article: FinBERT sentiment ∈ [0,1]
stress_raw = (mean_sentiment - 0.5) × log(1 + article_count)
scsi = stress_7d_rolling_mean - stress_30d_rolling_mean
```

### Inputs
- `df: DataFrame` — news articles with `sentiment` column (post-FinBERT scoring)
- Indexed by `[Date, Ticker]`

### Outputs
- `df[Date, Ticker, stress_raw, stress_7d, stress_30d, scsi]` — float columns

### Side Effects
- None

### Dependencies
- `pandas`, `numpy` — for rolling
- `FinBERT` — for upstream `score_articles()` step

### Coupling Risk
- LOW for formula; MEDIUM for FinBERT dependency

### Reuse Verdict
**B — Idea reuse.** Formula is sound. Rewrite: output must be `Decimal`, not float. FinBERT is an external model dependency — treat as optional DataPlane input. In MVP stub, `scsi = Decimal("0")` per ticker until real sentiment data flows.

---

## Candidate 14: FCFF Semi-Valuation

**File:** `src/fundamentals/semi_valuation.py`
**Lines:** 1–130
**Target Module:** EvaluationEngine (diagnostics), ScoringEngine (future)

### Formula
```
FCFF_raw = EBIT × (1 - tax_rate) + D&A + SBC - Capex - ΔNWC
R&D_amort = 20-quarter straight-line amortization
FCFF_adj = FCFF_raw + SBC - R&D_exp + amort
needs_edgar_audit = True if |FCFF_adj - FCFF_raw| / |FCFF_raw| > 0.15
```

### Inputs
- `ticker: str`
- `quarters_df: DataFrame` — quarterly financials with EBIT, D&A, SBC, Capex, NWC, R&D

### Outputs
- `df` with `FCFF_raw`, `FCFF_adj`, `needs_edgar_audit` columns
- Decimal math internally, appends float columns (output contamination)

### Coupling Risk
- LOW — only needs quarterly financials DataFrame

### Reuse Verdict
**B — Idea reuse.** FCFF formula with R&D capitalization is analytically sound. Useful as a fundamental quality signal in ScoringEngine. Rewrite: all output columns must be Decimal. The `needs_edgar_audit` flag pattern is excellent — maps to `reason_codes` in domain objects.

---

## Candidate 15: Universe Config

**File:** `config/universe.yaml`
**Lines:** 1–601
**Target Module:** UniverseGateway

### Structure
- 101 tickers across 7 pillars: `semis`, `equipment`, `materials`, `cloud_ai`, `industrial`, `logistics`, `end_markets`
- Per ticker: `name`, `ibkr_symbol`, `stance` (long/neutral/avoid), `pillar`
- Stance values observed: `"long"`, `"neutral"`, `"avoid"`

### Reuse Verdict
**A — Direct adapter source.** This is the production universe definition. UniverseGateway should load from this file (or its successor) to populate `Universe.tickers`. The 7-pillar structure is the sector taxonomy for aggregator sector caps.

---

## Candidate 16: Master Score Config

**File:** `config/technical_master_score.yaml`
**Lines:** 1–100
**Target Module:** ScoringEngine

### Key Values
```yaml
# Category weights (SSOT per header comment)
trend_weight: 0.40
momentum_weight: 0.30
volume_weight: 0.20
volatility_weight: 0.10
news_weight: 0.20   # ← DRIFT: strategy_params says 0.30

# Indicators per category
trend: [adx_norm, macd_norm]
momentum: [rsi_norm, willr_norm, stoch_k_norm, stoch_d_norm, roc_norm, cci_norm,
           momentum_5d_norm, momentum_20d_norm]
volume: [volume_ratio_norm, cmf_norm, obv_norm]
volatility: [atr_norm, bb_position_norm]

# Regime weight sets (expansion vs contraction)
regime_weights:
  expansion: {trend: 0.45, momentum: 0.25, volume: 0.20, volatility: 0.10}
  contraction: {trend: 0.30, momentum: 0.35, volume: 0.15, volatility: 0.20}
```

### Reuse Verdict
**A for structure; B for values.** This config is the canonical scoring schema. Use it to define `ExperimentParams` scoring weights. Resolve the drift with `strategy_params.yaml` before porting: `news_weight = 0.20` (this file wins as SSOT). Regime-specific weight sets are the right pattern for MarketState-conditional scoring.
