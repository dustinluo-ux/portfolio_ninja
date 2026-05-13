# ADR 0001: Stub Adapters for MVP

**Status:** Accepted
**Date:** 2026-05-13

## Context

portfolio_ninja must validate the full canonical pipeline (Universe → AuditRecord) without incurring external API costs or requiring broker credentials during MVP development. The system design requires two external integration boundaries:

1. **Data ingestion** — fetch OHLCV, news sentiment, and fundamental data per ticker
2. **Order execution** — submit orders to a broker

Both boundaries must be swappable across run modes (backtest / paper / live) without any change to domain logic. This requires an adapter pattern with abstract interfaces defined in the shared domain layer.

Budget ceiling: $0 external spend in MVP (CASE_FACTS Decision 15).

## Decision

We will implement two abstract adapter interfaces in `src/portfolio_ninja/domain/adapters.py`:

- `DataAdapter` (ABC): `fetch(universe: Universe, window_days: int) -> MarketDataset`
- `ExecutionAdapter` (ABC): `submit(intent: ExecutionIntent) -> None`

We will ship two stub implementations in `src/portfolio_ninja/domain/stubs.py`:

- `StubDataAdapter` — generates deterministic dummy OHLCV, news-sentiment, and fundamental data using a seeded RNG (`seed=42`). Same inputs always produce identical `MarketDataset` output. No external API calls.
- `StubExecutionAdapter` — logs the `ExecutionIntent` via the standard `logging` module and returns immediately. No broker API call.

Both stubs implement the abstract interfaces exactly. Swapping stubs for real adapters requires no changes to domain logic, module contracts, or the orchestrator beyond the adapter factory selection.

## Consequences

**Positive:**
- Full canonical pipeline is testable without any external dependencies or credentials
- Tests are reproducible and deterministic (fixed seed)
- Real data and broker integration can be introduced incrementally by implementing `DataAdapter` / `ExecutionAdapter` without touching domain logic
- Enforces the adapter pattern as a first-class architectural boundary from day one

**Negative:**
- Stub data does not reflect real market behavior; signal quality cannot be validated until a real `DataAdapter` is integrated
- Stub execution cannot validate order routing, fill simulation, or latency behavior

**Risks:**
- R007: `StubDataAdapter` produces non-deterministic data if RNG seed is not fixed — mitigation: seed RNG in `__init__` with `seed=42`; smoke test asserts output hash is identical across two calls with same inputs
- Any future adapter must implement the exact interface defined in `domain/adapters.py`; deviations require a new ADR
