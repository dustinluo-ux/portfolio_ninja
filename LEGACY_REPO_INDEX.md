# LEGACY_REPO_INDEX.md
# ai_supply_chain_trading — Repository Inventory
> Generated: 2026-05-13 | Read-only mine. New architecture contracts are frozen.

---

## 1. Folder Tree

```
ai_supply_chain_trading/
├── src/
│   ├── core/
│   │   ├── types.py          ← generic dict aliases (contamination — replace)
│   │   ├── state.py          ← PipelineState + VendorEvent (clean, reusable)
│   │   ├── intent.py         ← cross-module handoff (float contamination)
│   │   └── hedger.py         ← rolling OLS beta, Sharpe, MDD math
│   ├── data/
│   │   ├── base_provider.py  ← abstract DataProvider (float return type)
│   │   ├── provider_factory.py ← factory w/ silent fallback
│   │   ├── csv_provider.py   ← CSV loader (silent skip on missing)
│   │   ├── resilience_layer.py ← CSV→Marketaux→YFinance chain + Decimal cast
│   │   ├── data_quality.py   ← DataQualityReport, IncompleteDataError
│   │   ├── news_fetcher_factory.py ← news provider factory (hardcoded path)
│   │   ├── news_base.py
│   │   ├── news_sources/
│   │   │   └── base_provider.py
│   │   ├── eodhd_news_loader.py
│   │   ├── fmp_ingest.py
│   │   ├── edgar_audit.py
│   │   ├── contract_resolver.py
│   │   └── data_config.py (config ref only)
│   ├── execution/
│   │   ├── planner.py        ← CLEAN — Decimal throughout, MNQ+options overlay
│   │   ├── ibkr_nav.py       ← NAV fetch (float return, never raises)
│   │   ├── regime_controller.py ← SPY/200-SMA binary regime + atomic write
│   │   └── performance_logger.py ← DEAD — re-export shim only
│   ├── monitoring/
│   │   ├── regime_watcher.py ← polls JSON, Telegram alert
│   │   ├── structural_breakdown.py ← IC decay + residual + beta (3× bare except)
│   │   └── incident_logger.py ← append-only JSONL (clean)
│   ├── signals/
│   │   └── feature_engineering.py ← FinBERT → SCSI formula
│   ├── risk/
│   │   └── types.py          ← TargetPortfolio, RiskConstraints, FinalExecutionPlan (CLEAN)
│   ├── portfolio/
│   │   ├── position_sizer.py ← ATR sizing (float output)
│   │   └── pod_pnl_tracker.py ← Sharpe/MDD per pod (float throughout)
│   ├── fundamentals/
│   │   └── semi_valuation.py ← FCFF + R&D cap (Decimal internally, float out)
│   ├── models/
│   │   └── model_factory.py  ← ML registry (linear/ridge/lasso/XGB/CatBoost)
│   ├── agents/
│   │   ├── bull_bear_debate.py ← advisory debate scorer
│   │   ├── skeptic_gate.py   ← bear fundamental gate
│   │   ├── damodaran_anchor.py ← DCF/CAPM scorer (550 lines, yfinance-only)
│   │   └── taleb_auditor.py  ← tail risk + antifragility (978 lines, GOD FILE)
│   └── hedging/
│       ├── black_scholes_engine.py ← B-S put price + delta-strike solver
│       └── hedging_strategy.py ← TailHedge SMH put overlay
├── pods/
│   ├── pod_core.py           ← HRP + alpha tilt (float, silent fallback)
│   ├── meta_allocator.py     ← Bayesian softmax meta-allocation
│   ├── aggregator.py         ← sector/gross caps + directional veto
│   ├── pod_ballast.py        ← defensive cash+short sleeve
│   └── pod_extension.py      ← DEAD thin wrapper (broken import)
├── auditor/
│   ├── orchestrator.py       ← 4-stage audit pipeline (BOM→SEC→financials→TES)
│   ├── tdo_gate.py           ← 7-check execution eligibility gate
│   ├── tdo_gate.py
│   ├── bom_decomposer.py
│   ├── market_cap_lookup.py
│   ├── supply_chain_scraper.py
│   └── financial_fetcher.py
├── lib/
│   └── shared_core/
│       └── tes_scorer.py     ← TES formula (float output, patent stub)
├── config/
│   ├── universe.yaml         ← 101 tickers, 7 pillars, IBKR mappings
│   ├── technical_master_score.yaml ← scoring weights SSOT (drift conflicts exist)
│   ├── strategy_params.yaml  ← regime/rebalance/execution params (config drift)
│   ├── model_config.yaml     ← ML model, features, risk params, Track D
│   ├── trading_config.yaml   ← mode/IBKR/account (hardcoded account number)
│   ├── layered_signal_config.yaml ← layered signal (use_layered_engine: false)
│   ├── data_config.yaml
│   ├── instruments.yaml
│   └── optimizer_config.yaml
├── scripts/
│   ├── train_ml_model.py     ← standalone ML training runner
│   ├── run_risk_daily.py     ← daily risk snapshot → outputs/ (atomic write)
│   ├── refresh_tes_scores.py ← TES proxy scores → tes_scores.json
│   ├── scouting_module.py    ← news-based universe scouting
│   ├── update_universe.py    ← CLI universe management
│   ├── update_signal_db.py   ← signal DB update
│   ├── reconcile_fills.py    ← fill reconciliation
│   ├── check_data_integrity.py
│   ├── download_fundamentals.py
│   ├── fetch_tiingo_news.py
│   └── research/
│       ├── optimize_params.py
│       └── run_calibration.py
├── tests/
│   ├── test_tdo_validator.py ← full Red Team Constraint coverage
│   ├── test_tdo_gate.py      ← 10-scenario execution gate tests
│   ├── test_max_weight_cap.py ← HRP alpha tilt cap enforcement
│   ├── test_ibkr_live_provider.py ← IBKR provider unit tests (mocked)
│   └── test_tdo_bridge.py    ← bridge promotion integration tests
├── tdo_validator.py          ← TDO schema validation + Red Team Constraints
├── tdo_bridge.py             ← ThesisCandidate → TDO promotion
├── THESIS_SCHEMA.json        ← JSON schema v1.0.0
├── graveyard/
│   └── scripts/optimize_features.py ← DEAD feature tournament tool
├── outputs/                  ← backtest results, audit JSONs, frozen_pods.json
├── logs/models/              ← feature_importance_*.json
└── models/saved/
    └── catboost_20260308_103404.pkl
```

---

## 2. Important Entrypoints

| Script | Purpose | Atomic Write | Config Read |
|--------|---------|-------------|-------------|
| `scripts/train_ml_model.py` | ML model training + feature tournament | No | `model_config.yaml` |
| `scripts/run_risk_daily.py` | Daily risk snapshot → `outputs/risk_status.json` | Yes | `strategy_params.yaml`, `model_config.yaml` |
| `scripts/scouting_module.py` | News-based scouting → `outputs/pit_candidates.csv` | Yes | `strategy_params.yaml` |
| `scripts/refresh_tes_scores.py` | TES proxy scores → `outputs/tes_scores.json` | No | `auditor_config.yaml` |
| `scripts/update_universe.py` | Universe add/remove + data sync | Yes | `universe.yaml` |
| `auditor/orchestrator.py` | 4-stage TDO audit pipeline | No (mutates in place) | `auditor_config.yaml` |
| `scripts/reconcile_fills.py` | IBKR fill reconciliation | Unknown | `trading_config.yaml` |

---

## 3. Scripts Directory Summary

| Script | Status | Notes |
|--------|--------|-------|
| `train_ml_model.py` | Active | Research/batch tool |
| `run_risk_daily.py` | Active | Production-adjacent, atomic write |
| `scouting_module.py` | Active | Hardcoded DATA_DIR fallback |
| `refresh_tes_scores.py` | Active | TES stub (patent density = 0.10 constant) |
| `update_universe.py` | Active | Hardcoded Python executable path |
| `research/optimize_params.py` | Research only | Not production |
| `research/run_calibration.py` | Research only | Not production |
| `graveyard/scripts/optimize_features.py` | DEAD | Explicitly in graveyard/ |

---

## 4. Config Files

| File | Lines | Role | Drift Risk |
|------|-------|------|-----------|
| `universe.yaml` | 601 | 101-ticker universe, 7 pillars, IBKR symbol mappings | Low |
| `technical_master_score.yaml` | 100 | Master scoring weights SSOT — intended | HIGH — overridden by strategy_params |
| `strategy_params.yaml` | 87 | Regime, rebalance, execution, optimizer params | HIGH — conflicts with model_config and technical_master_score |
| `model_config.yaml` | 98 | ML model, features, risk thresholds, Track D spec | HIGH — paths machine-specific, Track A model path broken |
| `trading_config.yaml` | 57 | Mode, IBKR ports, account number, max position | HIGH — hardcoded account, max_position conflicts with Track D |
| `layered_signal_config.yaml` | 39 | Layered signal weights | LOW — entire system disabled (`use_layered_engine: false`) |
| `auditor_config.yaml` | Unknown | Auditor pipeline config | Unknown |
| `optimizer_config.yaml` | Unknown | Optimizer config | Unknown |

---

## 5. Test Files

| File | Scenarios | Coverage Target | Notes |
|------|-----------|----------------|-------|
| `test_tdo_validator.py` | Full Red Team Constraint suite | `tdo_validator.py` | Best test file in repo |
| `test_tdo_gate.py` | 10 scenarios: phase, hash, cap, 24h gate, market_cap, expiry, kill_switch | `auditor/tdo_gate.py` | Comprehensive |
| `test_max_weight_cap.py` | HRP alpha tilt cap at 0.40 | `pods/pod_core.py` | Narrow scope |
| `test_ibkr_live_provider.py` | Connect, NAV, prices, positions | `src/data/ibkr_live_provider.py` | Mocked ib_insync |
| `test_tdo_bridge.py` | Bridge promotion, fixture-driven | `tdo_bridge.py` | Integration tests |

---

## 6. Large / High-Coupling Files

| File | Lines | Coupling | Why |
|------|-------|---------|-----|
| `src/agents/taleb_auditor.py` | 978 | Low (yfinance-only) | GOD FILE — 7 sub-analyses, mixed responsibilities |
| `src/agents/damodaran_anchor.py` | 550 | Low (yfinance-only) | Large, yfinance dependency, self-contained |
| `src/portfolio/pod_pnl_tracker.py` | 316 | Medium | Reads fills, writes fitness, attribution logic |
| `src/monitoring/structural_breakdown.py` | 376 | Medium | 3 sub-assessments, all swallowed by bare excepts |
| `tdo_validator.py` | 469 | Medium | Referenced by bridge, gate, orchestrator |
| `tdo_bridge.py` | 367 | Low | Only calls validator |
| `config/universe.yaml` | 601 | HIGH | Foundation — read by universe gateway |

---

## 7. Suspicious Duplicate Logic

| Logic | Location 1 | Location 2 | Verdict |
|-------|-----------|-----------|--------|
| `news_weight` | `technical_master_score.yaml`: 0.20 | `strategy_params.yaml` optimizer: 0.30 | DRIFT — unresolved |
| `ml_blend_weight` | `model_config.yaml`: 0.30 | `strategy_params.yaml` optimizer: 0.10 | DRIFT |
| `three_layer_weight` | `strategy_params.yaml`: 0.30 | `layered_signal_config.yaml`: 0.40 | DRIFT (system disabled) |
| `trend_weight` | `technical_master_score.yaml`: 0.40 | `strategy_params.yaml` optimizer: 0.50 | DRIFT |
| `max_position` | `model_config.yaml` Track D: 0.10 | `trading_config.yaml`: 0.40 | DRIFT — 4× magnitude |
| Sharpe formula | `src/core/hedger.py` | `src/portfolio/pod_pnl_tracker.py` | DUPLICATE — both compute rolling Sharpe ×√252 |
| Atomic write pattern | `src/core/state.py` | `scripts/run_risk_daily.py` | DUPLICATE — correct pattern in both |
| Regime binary logic | `src/execution/regime_controller.py` | `pods/meta_allocator.py` (checks `regime_status`) | LAYERED — not duplicate, but implicit contract |

---

## 8. Likely Dead Code

| File/Function | Evidence | Verdict |
|--------------|---------|--------|
| `src/execution/performance_logger.py` | 7-line re-export shim, no logic | DEAD |
| `pods/pod_extension.py` | Imports `long_short_optimizer` which is not in repo | DEAD — broken import |
| `graveyard/scripts/optimize_features.py` | In `graveyard/` directory | DEAD — research artifact |
| `config/model_config.yaml` Track A model_path | `C:\Users\User\...` (wrong username) | DEAD — will fail to load |
| `config/strategy_params.yaml` three_layer_engine section | `use_layered_engine: false` at line 1 | DEAD — config unreachable |
| `auditor/orchestrator.py` `_guess_ticker()` | Only 2 hardcoded entries (ON, AAPL) | DEAD for all other tickers |
| `src/core/types.py` `Context` alias | Semantically identical to `DataContext` | DEAD — remove |
