# ADR 0004: SPY Auto-Inject for Regime Computation

## Status
Accepted

## Context

`MarketStateEngine._regime_signal()` requires SPY OHLCV bars (≥200) to compute the market regime (EXPANSION/CONTRACTION). Previously SPY was expected to be in `universe.tickers`, but this caused two problems:

1. `DataPlane.fetch_market_data()` raises `DataUnavailableError` if any ticker in `universe.tickers` is missing from the adapter's output. SPY CSV may not exist in backtest stores, causing all E2E tests to fail unless SPY data is always present.
2. SPY should never be scored or included in portfolio weights — it is a regime-signal-only ticker.

Adding SPY to `universe.tickers` would mix regime-only and scored tickers, breaking DataPlane's strict coverage enforcement and polluting scored output.

## Decision

Introduce a separate `regime_tickers: list[str]` field on `Universe` (default `[]`) and a corresponding `regime_data: dict[str, TickerData]` field on `MarketDataset` (default `{}`).

- **UniverseGateway** adds `"SPY"` to `regime_tickers` on every created Universe. SPY is never added to `universe.tickers`.
- **DataPlane** fetches `regime_tickers` best-effort after the primary `adapter.fetch()`. For each regime ticker, it creates a minimal single-ticker Universe and calls `adapter.fetch()` in a try-except. On any failure, it skips silently — MarketStateEngine already handles absent SPY gracefully (EXPANSION + `regime_spy_missing` reason_code).
- **MarketStateEngine** `_regime_signal()` reads from `dataset.regime_data.get("SPY")` instead of `dataset.data.get("SPY")`.
- SPY never appears in `MarketState.features` (features are built only from `dataset.data`).
- No change to `DataAdapter` ABC — the existing `fetch()` interface is reused with a single-ticker Universe.

### Dedup rule
If the caller includes `"SPY"` in `RunConfig.tickers`, UniverseGateway still puts SPY in `regime_tickers`. The DataPlane best-effort fetch is a no-op for tickers already in `dataset.data` if the same adapter is called twice.

## Consequences

- `Universe` gains one optional field (`regime_tickers`). All existing `Universe(...)` construction sites are backward-compatible (field has `default_factory=list`).
- `MarketDataset` gains one optional field (`regime_data`). All existing construction sites are backward-compatible (field has `default_factory=dict`).
- `_regime_signal()` behavior is unchanged when SPY is present in `regime_data`; graceful fallback is unchanged when absent.
- E2E tests without SPY CSV continue to pass — `regime_data` stays empty, regime defaults to EXPANSION.
- Future: if SPY CSV is added to the backtest store, regime computation activates automatically without any test change.
- 6 files changed: `domain/objects.py`, `universe_gateway.py`, `data_plane.py`, `market_state_engine.py`, `tests/test_universe_gateway.py`, `tests/test_e2e_universe_gateway.py`.
- Contracts updated: `universe_gateway.md`, `market_state_engine.md` (regime_data source change noted).
