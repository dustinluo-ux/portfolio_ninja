# LEGACY_MIGRATION_PLAN.md
# ai_supply_chain_trading → portfolio_ninja — Per-Module Migration Plan
> Generated: 2026-05-13 | Read-only mine. New architecture contracts are frozen.

---

## How to Read This Document

- **Reusable internals (A):** Port with minimal changes. Verify no contamination.
- **Reusable ideas (B):** Extract the algorithm or concept. Rewrite the implementation.
- **Rewrite candidates (C):** Correct logic, contaminated output. Rewrite to fix type/interface.
- **Deletion candidates (D):** Dead, broken, or duplicated. Delete without replacement.
- **Migration difficulty:** Easy (< 1 day), Medium (1–3 days), Hard (> 3 days)
- **Contamination risk:** from `LEGACY_CONTAMINATION_RISKS.md` — critical/high/medium/low

---

## Module 1: UniverseGateway

**Contract:** `docs/contracts/universe_gateway.md`  
**Migration difficulty:** Easy  
**Contamination risk:** Low

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| 101-ticker universe list | `config/universe.yaml` | Extract tickers + pillar assignments | Strip all runtime state fields (`promoted_at`, `source`); see CR-015 |
| 7 pillar definitions | `config/universe.yaml` | `pillars:` section | IBKR symbol mappings can be ignored for stub MVP |
| `UniverseValidator` logic | `tdo_validator.py` (lines ~1–50) | Max position ceiling constant: `MARKET_CAP_CEILING_USD = 50_000_000_000` | Extract constant, not the class |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| Pillar-based grouping | `universe.yaml` pillar keys | Use as `Universe.metadata["pillar"]` for downstream scoring context |
| Universe add/remove CLI | `scripts/update_universe.py` | Idea only — rewrite without hardcoded Python path |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `scripts/update_universe.py` hardcoded Python path | Machine-specific; broken on any other machine |
| `promoted_at` / `source` fields in config | Runtime state in config (CR-015) |

### Migration Notes

The ticker list in `universe.yaml` is clean and directly usable. Copy only the ticker symbols and pillar assignments. The new `Universe` domain object carries `tickers: list[str]` and `as_of_date`; everything else is derived at runtime. Do not copy IBKR symbol overrides — those belong in the ExecutionEngine adapter config.

---

## Module 2: DataPlane

**Contract:** `docs/contracts/data_plane.md`  
**Migration difficulty:** Medium  
**Contamination risk:** High (CR-003, CR-004, CR-005, CR-006)

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| `_cast_ohlc_to_decimal()` | `src/data/resilience_layer.py` | 12-line Decimal cast helper | Clean, no float contamination, no external deps |
| `DataQualityReport` dataclass | `src/data/data_quality.py` | Fields: `ticker`, `missing_fields`, `is_complete`, `reason` | Clean dataclass; rename fields to match `MarketDataset` lineage |
| `IncompleteDataError` | `src/data/data_quality.py` | Exception class with `ticker` + `reason` | Port as-is |
| Fallback chain structure | `src/data/resilience_layer.py` | CSV → external → YFinance order | Port the chain; replace bare excepts (CR-006) |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| 3-tier fallback chain | `resilience_layer.py` | Implement as `DataAdapter` chain with explicit logging at each fallback step |
| Data quality reporting | `data_quality.py` | Attach `DataQualityReport` to `MarketDataset.quality_report` |

### Rewrite Candidates (C)

| Asset | Legacy File | Problem | Rewrite Approach |
|-------|-------------|---------|-----------------|
| `DataProvider` base class | `src/data/base_provider.py` | `get_current_price() → float` (CR-003) | New `DataAdapter` ABC with `fetch() → MarketDataset` (Decimal) |
| `DataProviderFactory` | `src/data/provider_factory.py` | Silent fallback to CSV (CR-004) | New factory logs each fallback with named source |
| `CSVDataProvider.load_prices()` | `src/data/csv_provider.py` | Print-not-raise (CR-005) | Rewrite to raise `IncompleteDataError` |
| `_try_marketaux()` / `_try_yfinance()` | `src/data/resilience_layer.py` | Dual bare excepts (CR-006) | Replace with typed exception catches |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `DataContext = dict[str, Any]` | Generic dict alias (CR-001); no consumers in new arch |
| `src/data/news_fetcher_factory.py` | Hardcoded DATA_DIR path (CR-007); no stub equivalent needed |
| `src/data/eodhd_news_loader.py` | External API; out of scope for MVP |
| `src/data/fmp_ingest.py` | External API; out of scope for MVP |
| `src/data/edgar_audit.py` | External API; out of scope for MVP |
| `src/data/contract_resolver.py` | Unknown coupling; not needed for MVP |

### Migration Notes

The `_cast_ohlc_to_decimal()` helper and the `DataQualityReport`/`IncompleteDataError` pair are the highest-value portable pieces. The resilience chain concept is valuable but every implementation detail needs rewriting. Port the concept via ADR, not the code. The new `StubDataAdapter` generates deterministic dummy data and never calls any of the legacy providers.

---

## Module 3: MarketStateEngine

**Contract:** `docs/contracts/market_state_engine.md`  
**Migration difficulty:** Medium  
**Contamination risk:** Medium (CR-017)

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| Regime constants | `src/execution/regime_controller.py` | `BEAR_MULTIPLIER = 0.6`, `EXPANSION_MAX_LONGS = 5`, `CONTRACTION_MAX_LONGS = 3` | Extract constants only; no code |
| SCSI formula | `src/signals/feature_engineering.py` | `(mean_sentiment - 0.5) * log(1 + article_count)` | Extract formula as a pure function |
| `stress_7d - stress_30d` | `src/signals/feature_engineering.py` | Differential stress index | Pure arithmetic, no side effects |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| SPY/200-SMA binary regime | `regime_controller.py` | Port regime logic as `_compute_regime_signal()` — but data source must go through `DataAdapter`, not direct yfinance (CR-017) |
| EWMA volatility estimate | `pods/pod_core.py` | EWMA with `span=38` for vol scaling in MarketState features |
| Momentum feature | `config/technical_master_score.yaml` | `trend_weight: 0.40`, `momentum_weight: 0.30` as feature importance hints |

### Rewrite Candidates (C)

| Asset | Legacy File | Problem | Rewrite Approach |
|-------|-------------|---------|-----------------|
| `regime_controller.py` | `src/execution/regime_controller.py` | Live vs. backtest data divergence (CR-017) | Rewrite to accept `MarketDataset` from DataAdapter — no direct data fetching |
| `feature_engineering.py` | `src/signals/feature_engineering.py` | FinBERT dependency; yfinance dependency | Extract formulas only; stub news sentiment as Decimal("0.0") in MVP |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `src/monitoring/structural_breakdown.py` | 3× bare except pass (CR-012); ideas only, full rewrite |
| FinBERT integration in `feature_engineering.py` | External model; out of scope for stub MVP |

### Migration Notes

The regime binary and SCSI formula are the two core intellectual contributions of this module's legacy code. Both are simple arithmetic. Port the formulas as pure functions that accept `MarketDataset` as input and return typed feature fields on `MarketState`. The EWMA vol estimate from `pod_core.py` is a secondary feature; include it as `MarketState.volatility_ewma` for the scoring module to consume.

---

## Module 4: ScoringEngine

**Contract:** `docs/contracts/scoring_engine.md`  
**Migration difficulty:** Medium  
**Contamination risk:** High (CR-009, CR-008)

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| TES formula logic | `lib/shared_core/tes_scorer.py` | `revenue_ratio × (1+cagr) × patent_density` | Rewrite to return `Decimal` — do not port `float(result)` cast (CR-009) |
| Weight structure | `config/technical_master_score.yaml` | `trend: 0.40`, `momentum: 0.30`, `volume: 0.20`, `volatility: 0.10` | SSOT for scoring weights; ignore `strategy_params.yaml` overrides (CR-008) |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| Multi-factor composite score | `technical_master_score.yaml` + `model_config.yaml` | Score = weighted sum of (regime_adjusted_trend, momentum, volume, volatility) |
| ML blend weight | `model_config.yaml` | `ml_blend_weight: 0.30` — stub: ignore ML blend; set blend to 0 for MVP |
| News sentiment weight | `technical_master_score.yaml` | `news_weight: 0.20` — stub: use zero sentinel |

### Rewrite Candidates (C)

| Asset | Legacy File | Problem | Rewrite Approach |
|-------|-------------|---------|-----------------|
| `tes_scorer.py` | `lib/shared_core/tes_scorer.py` | Float return (CR-009) + constant stub (CR-014) | Rewrite: Decimal return, document `patent_density` stub |
| `model_factory.py` scoring path | `src/models/model_factory.py` | yfinance/live data dependency for features | Extract registry pattern (Class A for ExperimentEngine); scoring path is a rewrite |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `news_weight: 0.30` in `strategy_params.yaml` | Config drift (CR-008); `technical_master_score.yaml` is SSOT at 0.20 |
| `ml_blend_weight: 0.10` in `strategy_params.yaml` | Config drift; `model_config.yaml` at 0.30 is SSOT |
| `config/layered_signal_config.yaml` | Entire system disabled; do not port |

### Migration Notes

The TES formula and scoring weight structure are the reusable intellectual assets. The config drift (CR-008) must be resolved before implementing: use `technical_master_score.yaml` as the SSOT for weights. The MVP stub scorer uses seeded-RNG Decimal scores, so TES and ML blend are deferred to Phase V (real data integration). Port TES formula now so it is available for integration testing later.

---

## Module 5: ScoreArbitrationEngine

**Contract:** `docs/contracts/score_arbitration_engine.md`  
**Migration difficulty:** Easy  
**Contamination risk:** Medium

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| Gate threshold constants | `src/agents/skeptic_gate.py` | `PE_THRESHOLD = 35`, `PB_THRESHOLD = 5`, `DE_RATIO_THRESHOLD = 2`, `CURRENT_RATIO_MIN = 1.0`, `DRAWDOWN_THRESHOLD = -0.40` | Extract as typed constants |
| Gate logic structure | `src/agents/skeptic_gate.py` | 5-check fundamental gate: weight > 15% AND ≥2 flags AND ≥1 distress flag → FAIL | Port as pure function — no yfinance dependency |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| Multi-flag gate pattern | `skeptic_gate.py` | Apply gate as a post-ranking filter before `RankedUniverse` is emitted |
| Bear/bull debate scoring | `src/agents/bull_bear_debate.py` | Idea only: score each ticker by debate outcome; stub as Decimal("0.5") neutral |

### Rewrite Candidates (C)

| Asset | Legacy File | Problem | Rewrite Approach |
|-------|-------------|---------|-----------------|
| `skeptic_gate.py` full class | `src/agents/skeptic_gate.py` | yfinance data fetching inside the gate | Rewrite to accept pre-fetched fundamentals from `MarketDataset` |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `src/agents/bull_bear_debate.py` yfinance calls | External data dependency; stub the debate in MVP |
| `src/agents/damodaran_anchor.py` | 550 lines, yfinance-only; out of scope for MVP (see UNMAPPED) |

### Migration Notes

The skeptic gate constants are the highest-value portable asset. The gate logic itself is clean — the contamination is only that it fetches its own data via yfinance. Decouple the gate from data fetching: accept a `fundamentals` dict from `MarketDataset` and apply the threshold checks. This is a small rewrite, not a full redesign.

---

## Module 6: PortfolioConstructionEngine

**Contract:** `docs/contracts/portfolio_construction_engine.md`  
**Migration difficulty:** Hard  
**Contamination risk:** High (CR-010, CR-011)

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| Alpha tilt formula | `pods/pod_core.py` | `w_tilted[t] = w_hrp[t] × (score[t] / mean_score)` then renormalize | Extract formula only — no float; rewrite as Decimal arithmetic |
| HRP algorithm structure | `pods/pod_core.py` | Hierarchical Risk Parity with scipy linkage | Port the structure; replace numpy float output with Decimal normalization step |
| EWMA volatility span | `pods/pod_core.py` | `span=38` | Use as default; expose as config parameter |
| Sector cap logic | `pods/aggregator.py` | Max weight per sector | Port sector cap concept; rewrite to use Decimal weights |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| 3-pod architecture | `pods/pod_core.py` + `pod_ballast.py` + `meta_allocator.py` | Implement as a single `PortfolioConstructionEngine` in MVP; split to pods in Phase V |
| Bayesian meta-allocation | `pods/meta_allocator.py` | Idea for Phase V; not needed for equal-weight MVP stub |
| Gross cap enforcement | `pods/aggregator.py` | Max gross exposure check after weight computation |

### Rewrite Candidates (C)

| Asset | Legacy File | Problem | Rewrite Approach |
|-------|-------------|---------|-----------------|
| `pod_core.py` HRP weights | `pods/pod_core.py` | Float numpy output (CR-010) + silent HRP fallback (CR-011) | Rewrite: add Decimal normalization post-HRP; explicit error on HRP failure |
| `aggregator.apply_gross_caps()` | `pods/aggregator.py` | `dict[str, float]` signature (CR-010) | Rewrite: `dict[str, Decimal]` throughout |
| `meta_allocator.py` softmax | `pods/meta_allocator.py` | Float arithmetic; numpy | Rewrite as Decimal softmax for Phase V |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `pods/pod_extension.py` | Dead — broken import (`long_short_optimizer` does not exist) |
| `pods/pod_ballast.py` | Float throughout; defer to Phase V |

### Migration Notes

This is the hardest module to migrate. The HRP algorithm is the most complex portable piece — it uses scipy's hierarchical clustering, which produces numpy float arrays. The migration requires a post-processing Decimal normalization step after scipy outputs. For the MVP stub, use equal-weight construction (top-N tickers, `1/N` weight each as `Decimal`) and defer HRP to Phase V. The alpha tilt formula is simple enough to port directly as Decimal arithmetic in Phase V.

---

## Module 7: RiskEngine

**Contract:** `docs/contracts/risk_engine.md`  
**Migration difficulty:** Easy  
**Contamination risk:** Low

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| `TargetPortfolio` dataclass | `src/risk/types.py` | `weights: dict[str, Decimal]`, `as_of_date`, `strategy_id` | Decimal-clean; rename to match new domain object |
| `RiskConstraints` dataclass | `src/risk/types.py` | `max_position: Decimal`, `max_gross_exposure: Decimal`, `min_positions: int` | Clean; use `max_position = Decimal("0.10")` (Track D SSOT) |
| `FinalExecutionPlan` dataclass | `src/risk/types.py` | `approved: bool`, `adjustments: dict[str, Decimal]`, `reason_codes: list[str]` | Clean |
| Risk constraint checks | `tdo_validator.py` (Red Team constraints) | `MARKET_CAP_CEILING_USD`, `MAX_THESIS_AGE_DAYS`, `MIN_COMPOSITE_SCORE` | Extract constants |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| 7-check execution gate | `auditor/tdo_gate.py` | Port as `RiskEngine` pre-approval gate |
| MDD threshold check | `src/core/hedger.py` | Port max drawdown formula as a risk check |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `max_position: 0.40` in `trading_config.yaml` | Config drift (CR-008); Track D at 0.10 is SSOT |
| `src/execution/performance_logger.py` | 7-line dead re-export shim |

### Migration Notes

`src/risk/types.py` is the cleanest file in the legacy repo — pure dataclasses, Decimal throughout, no external deps. Port it directly as the basis for `RiskDecision` domain object. The `max_position` drift (CR-008: 0.10 vs. 0.40) is resolved by Track D SSOT: always use `Decimal("0.10")`. The 7-check TDO gate in `auditor/tdo_gate.py` maps naturally to the RiskEngine approval step.

---

## Module 8: ExecutionEngine

**Contract:** `docs/contracts/execution_engine.md`  
**Migration difficulty:** Easy  
**Contamination risk:** Medium (CR-002, CR-018)

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| `planner.py` order construction | `src/execution/planner.py` | Decimal-clean order construction; `BETA_GAP_THRESHOLD = Decimal("0.05")` | Best file in legacy repo — no contamination |
| MNQ/MES constants | `src/execution/planner.py` | `MNQ_MULTIPLIER = Decimal("2")`, `MES_MULTIPLIER = Decimal("5")` | Port as named constants |
| IBKR port config | `config/trading_config.yaml` | `paper_port: 7497`, `live_port: 7496` | Port port numbers; not the account number (CR-013) |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| Adapter pattern (paper vs. live) | `provider_factory.py` pattern | New `ExecutionAdapter` ABC + `StubExecutionAdapter` + future `IBKRExecutionAdapter` |

### Rewrite Candidates (C)

| Asset | Legacy File | Problem | Rewrite Approach |
|-------|-------------|---------|-----------------|
| `planner.py` input types | `src/execution/planner.py` | Receives `Intent.weights: dict[str, float]` (CR-002) | Rewrite to accept `ExecutionIntent.weights: dict[str, Decimal]` |
| `ibkr_nav.py` | `src/execution/ibkr_nav.py` | Never raises, returns `float | None` (CR-018) | Do not port; stub raises `ExecutionAdapterError` |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `src/core/intent.py` | `weights: dict[str, float]` at handoff boundary (CR-002); replaced by `ExecutionIntent` |
| `config/trading_config.yaml` account numbers | CR-013 — use env vars |

### Migration Notes

`planner.py` is the most directly portable file in the execution module. The only contamination is the `Intent` input type (float weights). Fix the input to accept `ExecutionIntent` (Decimal weights), and the internal logic is clean. The stub MVP does not need IBKR connectivity — the `StubExecutionAdapter` logs the intent and returns immediately. Port the planner's constant values and order construction logic for use when the real adapter is wired in Phase V.

---

## Module 9: EvaluationEngine

**Contract:** `docs/contracts/evaluation_engine.md`  
**Migration difficulty:** Medium  
**Contamination risk:** Medium (CR-009, float output from fundamentals)

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| Sharpe formula | `src/core/hedger.py` | `sharpe = mean_return / std_return × sqrt(252)` | Extract as pure function returning `Decimal` |
| MDD formula | `src/core/hedger.py` | Rolling max drawdown | Extract as pure function returning `Decimal` |
| Rolling OLS beta | `src/core/hedger.py` | Beta computation for hedging | Extract; useful for performance attribution |
| `pod_pnl_tracker.py` Sharpe | `src/portfolio/pod_pnl_tracker.py` | Duplicate of `hedger.py` Sharpe | DO NOT port — use `hedger.py` as SSOT |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| FCFF valuation | `src/fundamentals/semi_valuation.py` | Port formula; rewrite to return `Decimal` instead of `float` |
| R&D capitalization | `src/fundamentals/semi_valuation.py` | Amortized R&D adjustment to FCFF |
| Margin of safety check | `src/agents/damodaran_anchor.py` | `MoS threshold ±25%` — port as a constant |

### Rewrite Candidates (C)

| Asset | Legacy File | Problem | Rewrite Approach |
|-------|-------------|---------|-----------------|
| `semi_valuation.py` return type | `src/fundamentals/semi_valuation.py` | Float return from Decimal computation | Rewrite to return `Decimal` |
| `pod_pnl_tracker.py` | `src/portfolio/pod_pnl_tracker.py` | Float throughout; Sharpe formula duplicated from hedger | Use `hedger.py` formulas instead |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| Sharpe formula in `pod_pnl_tracker.py` | Duplicate of `hedger.py` — deduplicate |
| `src/agents/damodaran_anchor.py` yfinance calls | 550-line yfinance-only file; port only the MoS constant |
| `src/agents/taleb_auditor.py` (full) | 978-line god file; out of scope for MVP |

### Migration Notes

`hedger.py` contains the cleanest mathematical primitives in the legacy repo (rolling OLS beta, Sharpe, MDD). Port these as a `metrics` module under EvaluationEngine. The FCFF formula from `semi_valuation.py` is useful for Phase V when real fundamental data is connected. For MVP stub, `EvaluationReport.pnl = Decimal("0")` and `EvaluationReport.sharpe = Decimal("0")` — no computation needed.

---

## Module 10: ExperimentEngine

**Contract:** `docs/contracts/experiment_engine.md`  
**Migration difficulty:** Easy  
**Contamination risk:** Low

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| ML model registry pattern | `src/models/model_factory.py` | Registry dict `{name: (class, hyperparams)}` | Clean registry pattern; no contamination |
| Model type list | `src/models/model_factory.py` | `linear`, `ridge`, `lasso`, `xgboost`, `catboost` | Port as an enum or constant list |
| CatBoost model artifact | `models/saved/catboost_20260308_103404.pkl` | Loadable model from 2026-03-08 | Usable in Phase V if features match |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| Feature importance logging | `logs/models/feature_importance_*.json` | Port logging pattern to `ExperimentEngine.log_params()` |
| Hyperparameter injection | `config/model_config.yaml` | Inject params at experiment start, not hardcoded |
| ML blend weight | `model_config.yaml: 0.30` | Expose as `ExperimentParams.ml_blend_weight: Decimal("0.30")` |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `scripts/train_ml_model.py` | Standalone training script; not part of pipeline |
| `config/model_config.yaml` Track A model_path | Wrong username (CR-007); broken path |
| `graveyard/scripts/optimize_features.py` | Explicitly dead |

### Migration Notes

The `model_factory.py` registry pattern is the highest-value portable piece. Port it as the backbone of `ExperimentEngine` parameter injection. For MVP, `ExperimentParams` carries fixed defaults (no ML blend, no hyperparameter search). The CatBoost model artifact is loadable but only useful when the feature engineering pipeline (Phase V) produces matching features.

---

## Module 11: AuditMonitor

**Contract:** `docs/contracts/audit_monitor.md`  
**Migration difficulty:** Easy  
**Contamination risk:** Low (CR-016 only)

### Reusable Internals (A)

| Asset | Legacy File | What to Port | Notes |
|-------|-------------|--------------|-------|
| `tdo_validator.py` constants | `tdo_validator.py` | `MARKET_CAP_CEILING_USD`, `MIN_SUPPORTING_FINDINGS`, `MIN_COMPOSITE_SCORE`, `MAX_THESIS_AGE_DAYS`, `SAME_DAY_EXECUTION_GATE_HOURS = 24` | Clean constants, no contamination |
| `tdo_gate.py` 7-check gate | `auditor/tdo_gate.py` | phase, hash, cap, 24h, market_cap, expiry, kill_switch checks | Port logic; rename fields to match `AuditRecord` |
| `incident_logger.py` | `src/monitoring/incident_logger.py` | Append-only JSONL, never raises, atomic write | Near-perfect port candidate |
| `tdo_validator.py` Red Team constraints | `tdo_validator.py` | 15 validation rules with `ValidationResult` | Extract rules as a suite for `AuditRecord.validate()` |
| Atomic write in `state.py` | `src/core/state.py` | `.tmp → validate → os.replace()` pattern | Copy exact pattern |

### Reusable Ideas (B)

| Concept | Legacy Source | How to Apply |
|---------|--------------|-------------|
| 4-stage audit pipeline | `auditor/orchestrator.py` | BOM→SEC→financials→TES concept; stub as no-op in MVP |
| PipelineState lineage | `src/core/state.py` | `PipelineState` lineage tracking → thread into `AuditRecord.lineage_chain` |

### Deletion Candidates (D)

| Asset | Reason |
|-------|--------|
| `_guess_ticker()` in `orchestrator.py` | 2-entry hardcoded map (CR-016); delete entirely |
| `auditor/tdo_gate.py` (duplicate entry in folder) | `tdo_gate.py` listed twice in folder tree |
| `auditor/market_cap_lookup.py` | yfinance-only; stub for MVP |
| `auditor/supply_chain_scraper.py` | External scraper; out of scope |
| `auditor/financial_fetcher.py` | External API; out of scope |

### Migration Notes

`tdo_validator.py` is the most production-ready file in the legacy repo. Port its constants and validation rules directly into `AuditRecord.validate()`. The `incident_logger.py` atomic append pattern is the cleanest implementation of the atomic write rule in the legacy codebase — copy it verbatim. The `auditor/orchestrator.py` 4-stage pipeline concept is useful as a Phase V expansion; for MVP the AuditMonitor assembles lineage from upstream domain objects only.

---

## Cross-Cutting Migration Notes

### Decimal Rule Enforcement

Before porting any function, run this checklist:
1. Does the function receive `float` parameters? → Add `Decimal(str(x))` conversion at entry
2. Does the function return `float`? → Rewrite return to `Decimal`
3. Does the function use numpy/scipy math internally? → Add `Decimal(str(result))` normalization after computation
4. Does the function pass results to another function that expects `float`? → Fix the downstream interface first

### Bare Except Checklist

Before porting any try/except block:
1. Is the except `Exception` or bare `except:`? → Replace with specific exception types
2. Does the except block pass silently? → Add `logging.warning(f"...: {e}")` at minimum
3. Does the except return `None`? → Consider whether `None` is a valid sentinel or should be `raise`
4. Does the except log with `print()`? → Replace with `logging.error()`

### Config Drift Resolution

Do not port any YAML config file directly. Extract only the constant values needed by each module. Use these SSOT values:

| Parameter | SSOT Value | SSOT File |
|-----------|-----------|-----------|
| `news_weight` | 0.20 | `technical_master_score.yaml` |
| `trend_weight` | 0.40 | `technical_master_score.yaml` |
| `ml_blend_weight` | 0.30 | `model_config.yaml` |
| `max_position` | 0.10 | `model_config.yaml` Track D |
| `three_layer_engine_weight` | N/A (system disabled) | — |
| `patent_density` | 0.10 (stub) | `tes_scorer.py` default — document as stub |

### Phasing

| Phase | Scope | Migration Actions |
|-------|-------|------------------|
| MVP (current) | Stub adapters | Port constants and pure functions only. No legacy data fetching code. |
| Phase V | Real data integration | Port `resilience_layer` structure; wire `IBKRLiveProvider`; fix float→Decimal in provider boundary |
| Phase VI | Signal integration | Port TES, SCSI, Skeptic gate with real fundamental data from `MarketDataset` |
| Phase VII | ML integration | Load CatBoost model; port `model_factory` registry; wire feature pipeline |
| Phase VIII | HRP + alpha tilt | Port HRP with Decimal normalization; wire pod architecture |
