# LEGACY_MODULE_MAPPING.md
# ai_supply_chain_trading → portfolio_ninja Module Mapping
> Generated: 2026-05-13 | Classification key: A=direct reuse, B=idea only, C=rewrite, D=ignore/delete

Rules applied:
- New architecture contracts are frozen. Legacy code must not redefine architecture.
- No line evidence = no direct reuse claim.
- Prefer rewrite over contaminated reuse.
- Float in monetary/weight paths = minimum class C.

---

## Module 1: UniverseGateway

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| Universe ticker list (101 tickers, 7 pillars) | `config/universe.yaml` | **A** | Direct input feed — structure maps to `Universe.tickers` and pillar metadata |
| IBKR symbol mappings | `config/universe.yaml` (ibkr_symbol fields) | **A** | IBKR symbol resolution for live adapter |
| Universe stances (long/neutral/avoid) | `config/universe.yaml` (stance fields) | **B** | Idea — stance as pre-filter for ScoreArbitrationEngine |
| Universe pillar structure | `config/universe.yaml` (pillars: semis, equipment, etc.) | **B** | Idea — pillar labels usable for sector-cap enforcement |
| `scripts/update_universe.py` | `update_universe.py` | **C** | Rewrite: logic is correct (add/remove/sync) but has hardcoded Python path (`WEALTH_PY`) |
| `scripts/compare_universe.py` | `compare_universe.py` | **D** | Reconciliation utility, no architectural value |
| `scripts/sync_universe.py` | `sync_universe.py` | **D** | Data sync script, not a module |

---

## Module 2: DataPlane

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| `get_prices()` with CSV→Marketaux→YFinance chain | `src/data/resilience_layer.py` | **A** | Resilience pattern + Decimal cast after fetch is directly reusable |
| `_cast_ohlc_to_decimal()` | `src/data/resilience_layer.py` | **A** | Exact Decimal cast implementation |
| `DataQualityReport` + `IncompleteDataError` | `src/data/data_quality.py` | **A** | Quality contract types map directly to DataPlane output invariants |
| `CRITICAL_SOURCES` + `DEGRADED_SOURCES` constants | `src/data/data_quality.py` | **A** | Source criticality classification reusable verbatim |
| `BaseDataProvider` ABC | `src/data/base_provider.py` | **C** | Rewrite: interface is correct but `get_current_price() → float` must become `→ Decimal` |
| `CSVDataProvider.load_prices()` | `src/data/csv_provider.py` | **C** | Rewrite: silent skip on missing/short data must become explicit raise or logged skip |
| `DataProviderFactory.from_config_file()` | `src/data/provider_factory.py` | **C** | Rewrite: bare `except Exception` silent fallback to CSV is contamination |
| `VendorEvent` logging pattern | `src/core/state.py` | **B** | Idea — vendor event logging is the right pattern for DataPlane lineage |
| `PipelineState.fallback_count()` | `src/core/state.py` | **B** | Idea — fallback counting belongs in DataPlane adapter telemetry |
| News fetcher factory pattern | `src/data/news_fetcher_factory.py` | **C** | Rewrite: pattern is correct; hardcoded fallback path `C:/ai_supply_chain_trading/...` must go |
| `src/data/eodhd_news_loader.py` | `eodhd_news_loader.py` | **B** | Idea — EODHD news loading logic; review for adapter port |
| `scripts/download_fundamentals.py` | `download_fundamentals.py` | **D** | Batch download script, not a runtime module |
| `src/data/fmp_ingest.py` | `fmp_ingest.py` | **D** | FMP-specific ingest, paid API, not approved for MVP |
| `src/data/edgar_audit.py` | `edgar_audit.py` | **D** | EDGAR scraping, separate concern from DataPlane |

---

## Module 3: MarketStateEngine

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| Technical indicator column lists | `config/technical_master_score.yaml` (trend/momentum/volume/vol sections) | **A** | Exact list of indicator names maps to feature columns computed by MarketStateEngine |
| SCSI formula | `src/signals/feature_engineering.py` lines 44-70 | **B** | `stress_raw = (mean_sentiment - 0.5) × log(1+article_count)`, `scsi = stress_7d - stress_30d`. Idea — formula sound, output must be Decimal not float |
| `compute_daily_stress()` | `src/signals/feature_engineering.py` lines 44-48 | **B** | Idea — stress aggregation pattern; needs FinBERT dependency review |
| `compute_scsi()` | `src/signals/feature_engineering.py` lines 56-70 | **B** | Idea — rolling divergence signal pattern |
| `RegimeController.compute()` | `src/execution/regime_controller.py` | **B** | Idea — SPY/200-SMA regime classification; output (`regime_status` dict) should be a typed field on `MarketState` |
| `write_regime_status()` + atomic write pattern | `src/execution/regime_controller.py` | **A** | Atomic write pattern is correct; regime output format usable |
| Beta mandate thresholds | `config/model_config.yaml` lines 73-80 | **B** | Idea — beta bounds per strategy track inform RiskEngine, not MarketStateEngine |
| `config/layered_signal_config.yaml` | `layered_signal_config.yaml` | **D** | System disabled (`use_layered_engine: false`); do not port |

---

## Module 4: ScoringEngine

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| Master score formula weights | `config/technical_master_score.yaml` lines 3-8 | **A** | `trend=0.40, momentum=0.30, volume=0.20, volatility=0.10` — config-driven scoring weights |
| Master score formula pattern | `config/technical_master_score.yaml` + `strategy_params.yaml` | **C** | Rewrite: formula structure is valuable but must consolidate config drift before porting |
| News composite weight | `config/technical_master_score.yaml` line 10: `news_weight: 0.20` | **A** | Declared SSOT value (vs. 0.30 in strategy_params which is a drift artifact) |
| TES formula | `lib/shared_core/tes_scorer.py` | **C** | Rewrite: formula `revenue_ratio × (1+CAGR) × patent_density` is sound idea; must return Decimal; patent_density stub must be documented as limitation |
| `build_tes_components()` confidence tracking | `lib/shared_core/tes_scorer.py` | **B** | Idea — STUB/ESTIMATED/COMPUTED data confidence tagging maps to `reason_codes` in ScoreSet |
| Damodaran DCF score | `src/agents/damodaran_anchor.py` | **B** | Idea — MoS signal (UNDERVALUED if ≥25%, OVERVALUED if ≤-25%); rewrite: yfinance dependency, float output |
| `analyze_growth_and_reinvestment()` | `src/agents/damodaran_anchor.py` | **B** | Idea — 0-4 point growth scoring rubric |
| Taleb normalized score | `src/agents/taleb_auditor.py` | **B** | Idea — composite antifragility score (0-1 normalized); rewrite: 978-line god file, yfinance dependency |
| Individual Taleb sub-scores | `src/agents/taleb_auditor.py` (8 sub-analyses) | **B** | Ideas — each sub-analysis is extractable; prefer extracting primitives over importing god file |
| `config/model_config.yaml` ML model registry | `model_factory.py` + `model_config.yaml` | **B** | Idea — ML-scored signal as one input to ScoringEngine; CatBoost model at `models/saved/catboost_20260308_103404.pkl` is loadable |
| `src/models/model_factory.py` | `model_factory.py` | **A** | Registry pattern for ML models is reusable directly |
| `graveyard/scripts/optimize_features.py` | `optimize_features.py` | **D** | Graveyard — feature selection research, not a scoring module |

---

## Module 5: ScoreArbitrationEngine

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| Skeptic gate thresholds | `src/agents/skeptic_gate.py` lines 75-84 | **B** | Idea — bear fundamental gate (PE>35, PB>5, D/E>2, current_ratio<1, drawdown<-40%) as post-ranking filter |
| `run_gate()` logic | `src/agents/skeptic_gate.py` | **C** | Rewrite: yfinance dependency, float weights, SKIP on exception — needs deterministic path |
| `run_debate()` | `src/agents/bull_bear_debate.py` | **B** | Idea — advisory bull/bear scoring; binary thresholds (bull criteria: rev_growth>10%, ROE>10%, etc.) |
| `_compute_bull_score()` criteria | `src/agents/bull_bear_debate.py` lines 42-55 | **B** | Idea — 5 binary fundamental criteria each worth 0.2 |
| Meta-allocator Bayesian softmax | `pods/meta_allocator.py` | **B** | Idea — `F = sharpe/(1+|mdd|)`, softmax allocation; adapt as score weighting rather than pod allocation |
| Regime-based rank ceiling | `src/execution/regime_controller.py` (max_longs=3 in contraction) | **B** | Idea — regime-gated top-N cap maps to ExperimentParams.top_n override |
| Score floor (regime) | `src/execution/regime_controller.py` (score_floor=0.65/0.50) | **B** | Idea — minimum score threshold for inclusion in RankedUniverse |

---

## Module 6: PortfolioConstructionEngine

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| HRP algorithm | `pods/pod_core.py` (PyPortfolioOpt call) | **B** | Idea — HRP as alternative to equal-weight; requires `hrp_alpha_tilt()` rewrite to Decimal output |
| Alpha tilt formula | `pods/pod_core.py` lines 68-72: `w_tilted = w_hrp × (score / mean_score)` | **B** | Idea — score-proportional tilt; needs Decimal rewrite |
| EWMA vol scaling | `pods/pod_core.py` (span=38, λ≈0.94, clip [0.5, 1.0]) | **B** | Idea — vol-adjusted allocation; float contamination |
| Iterative max_position cap | `pods/pod_core.py` (redistribution loop) | **B** | Idea — cap redistribution loop is the right approach; rewrite in Decimal |
| Aggregator sector/gross caps | `pods/aggregator.py` (sector_cap=0.40, gross_cap=1.60) | **B** | Idea — cap enforcement post-aggregation; extract as risk rule for PortfolioConstructionEngine or RiskEngine |
| Bayesian shrinkage pattern | `pods/aggregator.py` (entropy-based shrinkage) | **B** | Idea — shrinkage toward equal-weight under uncertainty |
| ATR position sizing | `src/portfolio/position_sizer.py` | **C** | Rewrite: formula is sound (`w ∝ risk_pct × price / (ATR × mult)`) but float output; Decimal rewrite needed |
| Ballast defensive sleeve | `pods/pod_ballast.py` | **D** | Ignore for MVP — cash+short sleeve is out of scope per "no leverage" constraint |
| `pods/pod_extension.py` | `pod_extension.py` | **D** | DEAD — broken import, no upstream |
| Track D spec | `config/model_config.yaml` Track D section | **B** | Idea — `top_n=15, bottom_n=8, long_short_130_30` is the target strategy spec |

---

## Module 7: RiskEngine

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| `TargetPortfolio` domain type | `src/risk/types.py` | **A** | Clean frozen dataclass with Decimal weights — maps directly to new domain object |
| `RiskConstraints` domain type | `src/risk/types.py` | **A** | Beta cap, position scale, stop-loss flag all Decimal — direct reuse |
| `FinalExecutionPlan` domain type | `src/risk/types.py` | **A** | Decimal orders + typed overlay/option orders — template for ExecutionIntent |
| Stop-loss logic | `src/execution/planner.py` lines 68-72 | **A** | If `stop_loss_active → zero all weights`. Decimal-clean. |
| Position cap with redistribution | `pods/pod_core.py` iterative loop | **B** | Idea — iterative cap enforcement is better than clamp |
| TDO kill-switch check | `auditor/tdo_gate.py` (kill_switch_active check) | **A** | Direct reuse as risk gate |
| Market cap ceiling | `tdo_validator.py`: `MARKET_CAP_CEILING_USD = 50_000_000_000` | **B** | Idea — $50B cap as universe filter (belongs in UniverseGateway or RiskEngine per strategy) |
| IC decay circuit breaker | `src/monitoring/structural_breakdown.py` | **B** | Idea — IC-based circuit breaker concept; rewrite: bare excepts must go |
| Circuit breaker config | `config/strategy_params.yaml` (max_1d_drawdown_pct=0.05, enabled=true) | **B** | Idea — daily drawdown circuit breaker parameter |
| VIX multiplier | `config/strategy_params.yaml` (vix_elevated_threshold=28, multiplier=0.6) | **B** | Idea — VIX-based position scale-down |
| Beta gap threshold | `src/execution/planner.py`: `BETA_GAP_THRESHOLD = Decimal("0.05")` | **A** | Exact threshold value, Decimal-clean |
| `_compute_portfolio_beta()` | `src/execution/planner.py` | **A** | 60-day OLS per ticker, clamp [0,3], Decimal output — direct reuse |
| `config/model_config.yaml` stop-loss values | stop_loss_threshold=-0.10, per_position=0.08 | **B** | Idea — parameter values for RiskEngine configuration |
| Sector correlation threshold | `config/strategy_params.yaml` (sector_corr_threshold=0.85) | **B** | Idea — concentration risk signal |

---

## Module 8: ExecutionEngine

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| `ExecutionPlanner.reconcile()` | `src/execution/planner.py` | **A** | Core execution logic is Decimal-clean; MNQ/SMH overlay is future scope |
| `FinalExecutionPlan` | `src/risk/types.py` | **A** | Typed output object template — long_orders, overlay_orders, option_orders |
| `Intent` cross-module handoff | `src/core/intent.py` | **C** | Rewrite: structure is right, `weights: dict[str, float]` must be Decimal |
| IBKR NAV fetch | `src/execution/ibkr_nav.py` | **A** | Direct reuse for live adapter — paper/live port separation already present |
| IBKR symbol mappings | `config/universe.yaml` ibkr_symbol fields | **A** | Symbol resolution table for live adapter |
| Mode config (backtest/paper/live) | `config/trading_config.yaml` (mode field) | **B** | Idea — run_mode parameter maps to ExecutionEngine's run_mode invariant |
| Execution frequency + buffer | `config/strategy_params.yaml` (rebalance_weekly, buffer=0.01) | **B** | Idea — rebalance frequency config |
| `scripts/reconcile_fills.py` | `reconcile_fills.py` | **B** | Idea — fill reconciliation pattern for EvaluationEngine input |
| `scripts/test_execution_parity.py` | `test_execution_parity.py` | **D** | Ad-hoc parity test, not reusable module |

---

## Module 9: EvaluationEngine

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| `Hedger.apply_hedge()` | `src/core/hedger.py` | **B** | Idea — Sharpe and MDD formulas: `sharpe = (mean_r × periods_per_year) / (std_r × √periods_per_year)`, `mdd = min(cummax - cum) / cummax`. Needs Decimal rewrite |
| `_compute_fitness()` in pod_pnl_tracker | `src/portfolio/pod_pnl_tracker.py` | **B** | Idea — rolling 60-obs Sharpe ×√252; float throughout, needs Decimal rewrite |
| `SemiValuationEngine.compute()` | `src/fundamentals/semi_valuation.py` | **B** | Idea — FCFF + R&D capitalization as evaluation diagnostic; float output |
| Default fitness baselines | `src/portfolio/pod_pnl_tracker.py` (core sharpe=0.526, mdd=-0.094) | **B** | Idea — baseline comparison values for performance attribution |
| IC baseline | `config/model_config.yaml` (ic_baseline: 0.0428) | **B** | Idea — IC threshold for signal quality gate |
| Structural breakdown | `src/monitoring/structural_breakdown.py` | **C** | Rewrite: three IC/residual/beta sub-assessments are valuable; all wrapped in bare excepts that must be replaced |
| `incident_logger.py` | `src/monitoring/incident_logger.py` | **A** | Append-only JSONL incident log — direct reuse for EvaluationReport persistence |
| Backtest outputs format | `outputs/backtest_*.json` | **B** | Idea — output schema for EvaluationReport JSON representation |

---

## Module 10: ExperimentEngine

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| `src/models/model_factory.py` | `model_factory.py` | **A** | ML model registry (linear/ridge/lasso/XGB/CatBoost) — direct reuse for experiment model selection |
| `config/model_config.yaml` | `model_config.yaml` | **B** | Idea — track definitions (A/B/D), feature lists, training window are ExperimentParams sources |
| Track D spec | `config/model_config.yaml` Track D | **B** | Idea — `top_n=15, bottom_n=8, target_vol=0.4, max_leverage=1.6` as ExperimentParams |
| Feature list | `config/model_config.yaml` features section (7 features) | **B** | Idea — feature names map to MarketState fields |
| `scripts/train_ml_model.py` | `train_ml_model.py` | **B** | Idea — training runner pattern; extract as ExperimentEngine's model refresh trigger |
| `scripts/run_quarterly_retrain.py` | `run_quarterly_retrain.py` | **D** | Operational script, not a module |
| `graveyard/scripts/optimize_features.py` | `optimize_features.py` | **D** | DEAD — graveyard |

---

## Module 11: AuditMonitor

| Legacy Asset | File | Class | Rationale |
|-------------|------|-------|----------|
| `tdo_validator.py` | `tdo_validator.py` | **A** | TDO JSON Schema validation + Red Team Constraints + `compute_audit_hash()` — direct reuse |
| `THESIS_SCHEMA.json` | `THESIS_SCHEMA.json` | **A** | JSON schema v1.0.0 — canonical contract for TDO validation |
| `tdo_bridge.py` | `tdo_bridge.py` | **A** | ThesisCandidate → TDO promotion logic — direct reuse |
| `auditor/tdo_gate.py` | `tdo_gate.py` | **A** | 7-check execution eligibility gate — direct reuse |
| `auditor/orchestrator.py` | `auditor/orchestrator.py` | **A** | 4-stage audit pipeline — direct reuse (with `_guess_ticker()` rewrite) |
| `src/core/state.py` PipelineState | `state.py` | **A** | Lineage tracking, vendor events, fallback counts — maps to AuditRecord lineage fields |
| `src/monitoring/incident_logger.py` | `incident_logger.py` | **A** | Append-only JSONL incident log — direct reuse |
| `compute_audit_hash()` | `tdo_validator.py` | **A** | SHA-256 of canonical payload — already matches new `params_hash` pattern |
| `tests/test_tdo_validator.py` | `test_tdo_validator.py` | **A** | Comprehensive Red Team Constraint test suite — port directly |
| `tests/test_tdo_gate.py` | `test_tdo_gate.py` | **A** | 10-scenario gate tests — port directly |
| `tests/test_tdo_bridge.py` | `test_tdo_bridge.py` | **A** | Bridge integration tests — port directly |
| `auditor/bom_decomposer.py` | `bom_decomposer.py` | **B** | Idea — supply chain BOM decomposition for audit enrichment |
| `auditor/market_cap_lookup.py` | `market_cap_lookup.py` | **B** | Idea — market cap lookup for audit constraints |
| `src/monitoring/regime_watcher.py` | `regime_watcher.py` | **B** | Idea — regime change notification pattern; Telegram dependency is optional |
| `outputs/audit/*.json` | audit JSON outputs | **B** | Idea — AuditRecord JSON schema observed in practice |
| `auditor/supply_chain_scraper.py` | `supply_chain_scraper.py` | **D** | SEC scraping — external I/O, not MVP scope |
| `auditor/financial_fetcher.py` | `financial_fetcher.py` | **D** | External financial data fetch for auditor — not MVP scope |

---

## UNMAPPED Assets

| Asset | Reason |
|-------|--------|
| `src/hedging/black_scholes_engine.py` | Options pricing — out of MVP scope (no-leverage constraint) |
| `src/hedging/hedging_strategy.py` | SMH put tail hedge — out of MVP scope |
| `src/core/hedger.py` SMH-specific logic | SMH hedge overlay — out of MVP scope |
| `src/agents/taleb_auditor.py` full implementation | Too large (978 lines), yfinance-only; extract specific sub-analyses when needed |
| `src/agents/damodaran_anchor.py` full implementation | yfinance-only; extract DCF formula when integrating real data |
| `config/trading_config.yaml` paper_account field | Hardcoded account number must not be ported |
| `scripts/register_regime_watcher_task.ps1` | OS-specific scheduler script |
| `auditor/orchestrator.py` `_guess_ticker()` | 2-entry hardcoded map — replace with proper symbol resolver |
