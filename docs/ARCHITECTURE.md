# Architecture: portfolio_ninja

## Canonical Decision Path

```
Universe → MarketDataset → MarketState → ScoreSet → RankedUniverse
→ TargetPortfolio → RiskDecision → ExecutionIntent
→ EvaluationReport → AuditRecord
```

ExperimentEngine is a **side-input node**: it feeds `ExperimentParams` into ScoringEngine and PortfolioConstructionEngine. It is not a linear step in the main chain.

---

## Module List

| Module | Purpose | Complexity | Parallel? | Depends On |
|--------|---------|-----------|-----------|-----------|
| domain | Shared typed domain objects, adapter ABCs, and stub implementations | M | yes (no module deps) | none |
| UniverseGateway | Accepts external ticker list + run config; emits validated `Universe` | S | no | domain |
| DataPlane | Fetches OHLCV/news/fundamentals via adapter; emits `MarketDataset` | M | no | UniverseGateway, domain |
| MarketStateEngine | Computes per-ticker features (momentum, volatility, RSI) from `MarketDataset`; emits `MarketState` | M | no | DataPlane, domain |
| ExperimentEngine | Loads or constructs `ExperimentParams` (model_id, top_n, rebalance_freq); emits to ScoringEngine and PortfolioConstructionEngine | S | side-input resolved before scoring begins | domain |
| ScoringEngine | Scores each ticker using model identified in `ExperimentParams`; emits `ScoreSet` | M | no | MarketStateEngine, ExperimentEngine, domain |
| ScoreArbitrationEngine | Resolves multi-model conflicts; ranks tickers; emits `RankedUniverse` | S | no | ScoringEngine, domain |
| PortfolioConstructionEngine | Constructs target weights from `RankedUniverse` + `ExperimentParams`; emits `TargetPortfolio` | M | no | ScoreArbitrationEngine, ExperimentEngine, domain |
| RiskEngine | Validates `TargetPortfolio` against risk rules (no-leverage, exposure limits); emits `RiskDecision` | M | no | PortfolioConstructionEngine, domain |
| ExecutionEngine | Translates `RiskDecision` to orders; submits via adapter; emits `ExecutionIntent` | M | no | RiskEngine, domain |
| EvaluationEngine | Computes cycle PnL/Sharpe/drawdown from `ExecutionIntent`; emits `EvaluationReport` | M | no | ExecutionEngine, domain |
| AuditMonitor | Assembles full lineage from all upstream objects; emits `AuditRecord` (terminal) | S | no | EvaluationEngine, domain |

---

## Execution Graph

```
[domain] ─────────────────────────────────────────────────────── (shared dependency: all modules)

[domain] ──► [UniverseGateway] ──► [DataPlane] ──► [MarketStateEngine]
                                                             │
                                          [ExperimentEngine]─┤ (side-input)
                                                             ▼
                                                     [ScoringEngine] ──► [ScoreArbitrationEngine]
                                                                                   │
                                          [ExperimentEngine]───────────────────────┤ (side-input)
                                                                                   ▼
                                                                   [PortfolioConstructionEngine]
                                                                             │
                                                                       [RiskEngine]
                                                                             │
                                                                    [ExecutionEngine]
                                                                             │
                                                                   [EvaluationEngine]
                                                                             │
                                                                     [AuditMonitor] ──► AuditRecord (terminal)
```

Sequential execution enforced. No parallelism in the main chain. ExperimentEngine resolves before ScoringEngine begins.

---

## Module Map

| Module | Source Path | Contract Path | Upstream | Downstream | Domain Object In | Domain Object Out |
|--------|------------|--------------|----------|------------|-----------------|------------------|
| UniverseGateway | `src/portfolio_ninja/universe_gateway/` | `docs/contracts/universe_gateway.md` | external (ticker list + RunConfig) | DataPlane | — | `Universe` |
| DataPlane | `src/portfolio_ninja/data_plane/` | `docs/contracts/data_plane.md` | UniverseGateway | MarketStateEngine | `Universe` | `MarketDataset` |
| MarketStateEngine | `src/portfolio_ninja/market_state_engine/` | `docs/contracts/market_state_engine.md` | DataPlane | ScoringEngine | `MarketDataset` | `MarketState` |
| ExperimentEngine | `src/portfolio_ninja/experiment_engine/` | `docs/contracts/experiment_engine.md` | RunConfig | ScoringEngine, PortfolioConstructionEngine (side-input) | RunConfig | `ExperimentParams` |
| ScoringEngine | `src/portfolio_ninja/scoring_engine/` | `docs/contracts/scoring_engine.md` | MarketStateEngine, ExperimentEngine | ScoreArbitrationEngine | `MarketState`, `ExperimentParams` | `ScoreSet` |
| ScoreArbitrationEngine | `src/portfolio_ninja/score_arbitration_engine/` | `docs/contracts/score_arbitration_engine.md` | ScoringEngine | PortfolioConstructionEngine | `ScoreSet` | `RankedUniverse` |
| PortfolioConstructionEngine | `src/portfolio_ninja/portfolio_construction_engine/` | `docs/contracts/portfolio_construction_engine.md` | ScoreArbitrationEngine, ExperimentEngine | RiskEngine | `RankedUniverse`, `ExperimentParams` | `TargetPortfolio` |
| RiskEngine | `src/portfolio_ninja/risk_engine/` | `docs/contracts/risk_engine.md` | PortfolioConstructionEngine | ExecutionEngine | `TargetPortfolio` | `RiskDecision` |
| ExecutionEngine | `src/portfolio_ninja/execution_engine/` | `docs/contracts/execution_engine.md` | RiskEngine | EvaluationEngine | `RiskDecision` | `ExecutionIntent` |
| EvaluationEngine | `src/portfolio_ninja/evaluation_engine/` | `docs/contracts/evaluation_engine.md` | ExecutionEngine | AuditMonitor | `ExecutionIntent` | `EvaluationReport` |
| AuditMonitor | `src/portfolio_ninja/audit_monitor/` | `docs/contracts/audit_monitor.md` | EvaluationEngine | terminal | `EvaluationReport` | `AuditRecord` |

---

## Domain Object Layer

Location: `src/portfolio_ninja/domain/` — shared, no module dependency. No module may import from another module's source path; all cross-module handoffs use only types from this layer.

### Typed Domain Objects (dataclasses)

All monetary, weight, and price fields use `decimal.Decimal`. Never `float`.

| Object | Key Fields | Lineage Fields |
|--------|-----------|---------------|
| `Universe` | `tickers: list[str]`, `run_mode: str`, `window_days: int` | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `MarketDataset` | `data: dict[str, TickerData]` (`TickerData`: `ohlcv: list[OHLCVBar]`, `news_sentiment: Decimal`, `pe_ratio: Decimal`), `source_data_version: str` | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `MarketState` | `features: dict[str, TickerFeatures]` (`TickerFeatures`: `momentum_20d: Decimal`, `volatility_20d: Decimal`, `rsi_14: Decimal`) | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `ExperimentParams` | `scoring_model_id: str`, `top_n: int`, `rebalance_freq: str` | `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `ScoreSet` | `scores: dict[str, Decimal]`, `model_id: str` | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `RankedUniverse` | `ranked: list[tuple[str, Decimal]]` | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `TargetPortfolio` | `weights: dict[str, Decimal]` (MUST sum to `Decimal("1.0")`) | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `RiskDecision` | `approved: bool`, `weights: dict[str, Decimal]`, `adjustments: list[str]` | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `Order` | `ticker: str`, `direction: str` ("buy"/"sell"), `quantity: Decimal`, `order_type: str` ("market") | — |
| `ExecutionIntent` | `orders: list[Order]`, `adapter_id: str`, `run_mode: str` | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `EvaluationReport` | `cycle_id: str`, `pnl: Decimal`, `sharpe: Decimal`, `max_drawdown: Decimal` | `as_of_date: date`, `params_hash: str`, `validation_status: str`, `reason_codes: list[str]` |
| `AuditRecord` | `cycle_id: str`, `run_mode: str`, `tickers: list[str]`, `pipeline_hashes: dict[str, str]`, `completed_at: datetime` | `validation_status: str`, `reason_codes: list[str]` |

### Adapter Interfaces (`src/portfolio_ninja/domain/adapters.py`)

| Interface | Method Signature |
|-----------|-----------------|
| `DataAdapter` (ABC) | `fetch(universe: Universe, window_days: int) -> MarketDataset` |
| `ExecutionAdapter` (ABC) | `submit(intent: ExecutionIntent) -> None` |

### Stub Implementations (`src/portfolio_ninja/domain/stubs.py`)

| Stub | Behavior |
|------|---------|
| `StubDataAdapter` | Deterministic dummy OHLCV/news/fundamentals; seeded RNG (`seed=42`); same inputs always produce same output |
| `StubExecutionAdapter` | Logs `ExecutionIntent` via `logging` module; returns immediately; no broker call |

---

## Shared Resources

| Resource | Used By | Constraint |
|----------|---------|-----------|
| `src/portfolio_ninja/domain/` (types) | All 11 modules | Domain layer (M1) must be implemented and approved before any pipeline module build begins |
| `AuditRecord.pipeline_hashes` | AuditMonitor reads hashes from all upstream objects | AuditMonitor must run last; integrator confirms pipeline_hashes completeness |

---

## Milestones and SPOFs

| Milestone | Modules | SPOF | Mitigation |
|-----------|---------|------|-----------|
| M1: Domain layer | `domain/` (objects, adapters, stubs) | Domain object schema — if field types are wrong, all downstream contracts break | Contract tests assert every field type and `validate()` on construction |
| M2: Ingestion | UniverseGateway, DataPlane | `StubDataAdapter` reproducibility — if non-deterministic, tests are flaky | Seed RNG globally to 42; smoke test asserts output hash is identical across two calls with same inputs |
| M3: Feature + Experiment | MarketStateEngine, ExperimentEngine | `ExperimentParams` injection — if ExperimentEngine output is silently ignored, wrong model runs | Smoke test asserts `model_id` in `ScoreSet` matches `ExperimentParams.scoring_model_id` |
| M4: Scoring + Ranking | ScoringEngine, ScoreArbitrationEngine | Score arithmetic precision — if `Decimal` is dropped anywhere, ranking is wrong | Lint gate blocks `float(` near score fields |
| M5: Portfolio + Risk | PortfolioConstructionEngine, RiskEngine | Weight normalization — if weights do not sum to `Decimal("1.0")`, risk check must catch it | `RiskDecision.validate()` raises if `sum(weights.values()) != Decimal("1.0")` |
| M6: Execution + Eval + Audit | ExecutionEngine, EvaluationEngine, AuditMonitor | Lineage chain completeness — if any upstream hash is missing from `AuditRecord`, audit is incomplete | `AuditRecord.validate()` asserts `pipeline_hashes` has an entry for every domain object type in the canonical chain |

---

## Mode Switching

`RunConfig.run_mode`: `"backtest"` | `"paper"` | `"live"`

| Mode | DataAdapter | ExecutionAdapter |
|------|------------|-----------------|
| backtest | `StubDataAdapter` (or CSV adapter) | `StubExecutionAdapter` |
| paper | real `DataAdapter` | `StubExecutionAdapter` |
| live | real `DataAdapter` | real `ExecutionAdapter` (broker) |

Domain logic is identical across all modes. Mode flag is validated at orchestrator entry. Adapter selection is performed by a factory function; no mode-specific branches exist inside domain modules.

---

## Known Limitations (MVP)

- All data is dummy (`StubDataAdapter`); real data requires adapter swap — no domain logic changes needed
- All execution is stubbed (`StubExecutionAdapter`); real broker requires adapter swap — no domain logic changes needed
- Scoring is placeholder (ticker-hash-based Decimal score); real model requires ScoringEngine contract update + new ADR
- Options not implemented in MVP; options adapter is future work (explicit out of scope)
- No persistence layer; all state is in-memory per run
- No concurrent runs; single-process, sequential pipeline
- No real-time streaming; batch run per invocation

---

## Open Design Questions

None. All decisions recorded in `docs/CASE_FACTS.md` (Decisions 1–16, all resolved 2026-05-13) and `docs/adr/0001-stub-adapters-for-mvp.md`.
