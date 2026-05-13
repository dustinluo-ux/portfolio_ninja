# Contract: MarketStateEngine

## Purpose
Compute per-ticker technical features (20-day momentum, 20-day volatility, 14-day RSI) from a `MarketDataset`; emit a typed, lineage-annotated `MarketState`.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `dataset` | `MarketDataset` | DataPlane | yes | Full OHLCV/news/fundamentals for all tickers; must have `validation_status == "valid"` |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `market_state` | `MarketState` | ScoringEngine | Per-ticker `TickerFeatures` (momentum, volatility, RSI) for every ticker in the dataset |

## Dependencies
- `domain` — provides `MarketDataset`, `MarketState`, `TickerFeatures`, `OHLCVBar` types
- `DataPlane` — must have approved contract; provides `MarketDataset` input

## Invariants
- `market_state.features` has an entry for every ticker in `dataset.data`; raises `KeyError` if a ticker is unexpectedly absent during processing
- All feature values (`momentum_20d`, `volatility_20d`, `rsi_14`) are `decimal.Decimal`; never `float`
- `momentum_20d` is computed as `(close[-1] - close[-21]) / close[-21]` using the last 21 close prices (20-day return); requires at least 21 bars
- `volatility_20d` is the `Decimal` standard deviation of the last 20 daily close-to-close returns; requires at least 21 bars
- `rsi_14` is the 14-period RSI computed from close prices; requires at least 15 bars; value is in `[Decimal("0"), Decimal("100")]`
- If a ticker has insufficient bars for any feature computation, raises `InsufficientDataError` with `reason_codes` populated with `"insufficient_bars:{ticker}:needed:{N}:got:{M}"`
- `market_state.validation_status == "valid"` on successful exit
- `market_state.as_of_date == dataset.as_of_date`
- `market_state.params_hash` is SHA-256 hex of `(dataset.params_hash, "market_state_engine_v1")`
- `market_state.reason_codes` is an empty list on success
- Monetary values: Decimal only, never float
- No external I/O; purely in-memory computation

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| Ticker has fewer than 21 OHLCV bars (momentum/volatility) | M | H | Raises `InsufficientDataError` with ticker name and bar counts in message |
| Ticker has fewer than 15 OHLCV bars (RSI) | M | H | Raises `InsufficientDataError` with ticker name and bar counts in message |
| Division by zero in momentum (prior close == 0) | L | H | Raises `DataIntegrityError("close price is zero for ticker {ticker} at {date}")` |
| Ticker missing from `dataset.data` during iteration | L | H | Raises `KeyError(f"ticker {ticker} not found in MarketDataset")` |
| RSI computation produces value outside [0, 100] due to floating-point intermediate | L | M | Clamp to `[Decimal("0"), Decimal("100")]` after conversion; populate `reason_codes` with `"rsi_clamped:{ticker}"` |

## Tests Required
- [ ] `test_market_state_engine_valid_dataset_returns_complete_market_state`
- [ ] `test_market_state_engine_features_has_entry_for_every_ticker`
- [ ] `test_market_state_engine_all_feature_values_are_decimal`
- [ ] `test_market_state_engine_insufficient_bars_raises_insufficient_data_error`
- [ ] `test_market_state_engine_rsi_14_is_within_zero_to_hundred_bounds`
- [ ] `test_market_state_engine_momentum_20d_computed_correctly`
- [ ] `test_market_state_engine_volatility_20d_computed_correctly`
- [ ] `test_market_state_engine_validation_status_is_valid_on_success`
- [ ] `test_market_state_engine_params_hash_is_deterministic`

## Acceptance Criteria
- [ ] Returns `MarketState` with an entry in `features` for every ticker in `dataset.data`
- [ ] `validation_status == "valid"` on success
- [ ] All feature values are `decimal.Decimal`; no `float` in output
- [ ] Raises `InsufficientDataError` when any ticker has fewer than 21 bars (momentum/volatility) or 15 bars (RSI)
- [ ] `rsi_14` is always in `[Decimal("0"), Decimal("100")]`
- [ ] `market_state.as_of_date == dataset.as_of_date`

## Upstream Providers
- DataPlane (provides `MarketDataset`)

## Downstream Consumers
- ScoringEngine (consumes `MarketState`)
