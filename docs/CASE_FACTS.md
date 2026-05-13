# Case Facts — portfolio_ninja

<!--
INSTRUCTIONS FOR MANUFACTURE PIPELINE:
- Fill all fields before invoking any subagent.
- Subagents must prepend this file verbatim to their context — no summarizing, no paraphrasing.
- Source of truth for project identity, decisions made, and constraints in force.
-->

## Project Identity

**Name:** portfolio_ninja
**One-line description:** Automated stock-selection and portfolio-decision system — single-process, deterministic Python application with a sealed 11-module canonical pipeline.
**Owner:** dustinluo@gmail.com
**Initialized:** 2026-05-13

## Business Context

portfolio_ninja is a research-grade, production-capable automated stock-selection and portfolio-decision system. It accepts an externally supplied ticker universe and runs one canonical decision path:

```
Universe → MarketDataset → MarketState → ScoreSet → RankedUniverse
→ TargetPortfolio → RiskDecision → ExecutionIntent
→ EvaluationReport → AuditRecord
```

The same pipeline runs in backtest, paper, and live modes. Only the data source adapter and execution adapter differ between modes — all domain logic is identical and deterministic.

The system is designed as a single-process Python monolith. No services, no event buses, no async orchestration, no dashboards, no distributed components. Fail-loud: no silent fallbacks, no hidden default data, no implicit config drift. Every output object carries full lineage (source data version, as-of date, parameters used, validation status, reason codes).

## Decisions Made (binding)

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | Single-process Python monolith, no services or event buses | Simplicity and determinism; no distributed complexity for MVP | 2026-05-13 |
| 2 | Canonical decision path: Universe → MarketDataset → MarketState → ScoreSet → RankedUniverse → TargetPortfolio → RiskDecision → ExecutionIntent → EvaluationReport → AuditRecord | One path for all run modes; only adapters differ | 2026-05-13 |
| 3 | Backtest/paper/live modes share identical domain logic; only data source adapter and execution adapter differ | Prevents mode-specific bugs and ensures parity | 2026-05-13 |
| 4 | No generic dicts between modules — typed domain objects only for all cross-module handoffs | Compile-time-checkable interfaces; prevents silent schema drift | 2026-05-13 |
| 5 | Sealed node architecture — cross-node contracts do not change without an explicit ADR in `docs/adr/` | Prevents rabbit-hole experimentation from breaking adjacent modules | 2026-05-13 |
| 6 | Fail-loud: no silent fallbacks, no hidden defaults, no implicit config drift — raise on every unexpected condition | Forces explicit handling of every failure mode | 2026-05-13 |
| 7 | Every output object carries lineage: source_data_version, as_of_date, params_hash, validation_status, reason_codes | Full auditability and reproducibility | 2026-05-13 |
| 8 | MVP = architecture skeleton: typed domain objects, module folders, node contracts, validators, dummy implementations, one orchestrator, contract tests, smoke tests | Validates the full canonical path before introducing real data/logic | 2026-05-13 |
| 9 | HEAVY kit selected | 11 interdependent sealed modules with strict ADR governance require risk-checker and full pipeline | 2026-05-13 |
| 10 | Modules: UniverseGateway, DataPlane, MarketStateEngine, ScoringEngine, ScoreArbitrationEngine, PortfolioConstructionEngine, RiskEngine, ExecutionEngine, EvaluationEngine, ExperimentEngine, AuditMonitor | Covers full canonical path plus experiment control and audit | 2026-05-13 |
| 11 | No services, event buses, async orchestration, dashboards, distributed components, or framework-heavy abstractions | Out of scope for MVP and architectural philosophy | 2026-05-13 |
| 12 | Data sources: stub-only for MVP; StubDataAdapter (seeded RNG, seed=42) generates deterministic dummy OHLCV/news/fundamentals | Zero external spend; reproducible tests; adapter interface allows future swap | 2026-05-13 |
| 13 | Execution adapter: stub-only for MVP; StubExecutionAdapter logs intent and returns (no broker API) | Paper trading first; live trading via adapter swap without domain logic changes | 2026-05-13 |
| 14 | History/training window: configurable via RunConfig; default 730 days (2 years); dummy data only in MVP | Configurable without code changes; real data later via adapter swap | 2026-05-13 |
| 15 | Budget ceiling: $0 / no external spend in MVP; BUDGET_USD kill switch honored if env var set | No API cost exposure during development | 2026-05-13 |
| 16 | Compliance: long/short equities; no leverage (net exposure ≤ 1.0 enforced by RiskEngine); options possible via future adapter; paper → live via adapter swap | Minimal compliance surface for MVP while preserving upgrade path | 2026-05-13 |

## Open Questions (human-gate required)

None — all resolved 2026-05-13.

## Key Constraints

- **Data sources approved:** Stub-only for MVP. StubDataAdapter generates deterministic dummy OHLCV, news-sentiment, and fundamental data via seeded RNG (seed=42). No external API calls in MVP.
- **APIs approved:** None for MVP. Zero external spend. Adapter interface supports future swap to yfinance, Alpaca, Polygon, or custom CSV without domain logic changes.
- **History / training window:** Configurable via RunConfig; default 730 days (2 years). Dummy data only — no real historical pull in MVP.
- **Budget ceiling:** $0. No paid APIs, no external spend. Kill switch: if BUDGET_USD env var is set, halt before any tool use that would breach it.
- **Compliance requirements:** Long/short equities; no leverage (RiskEngine enforces net exposure ≤ 1.0 Decimal); options trading possible (future adapter); paper trading first; live trading via adapter swap (same domain logic). No FINRA/SEC-specific constraints enforced in MVP beyond no-leverage invariant.

## Out of Scope (explicit)

- Services, microservices, event buses, message queues
- Async orchestration (asyncio, Celery, Prefect, Airflow, etc.)
- Dashboards, web UIs, REST APIs
- Distributed components or multi-process coordination
- Framework-heavy abstractions (Django, FastAPI, etc.)
- Real brokerage connections in MVP — dummy execution adapter only
- Real external data source connections in MVP — dummy/fixture data only
- Machine learning model training or model management (scoring uses placeholder logic in MVP)
- Portfolio optimization solvers (placeholder in MVP)
- Real-time streaming data
