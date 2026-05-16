# Contract: MarketStateEngine

## Purpose
Compute per-ticker technical features (20-day momentum, 20-day volatility, 14-day RSI, EWMA volatility span=38, SCSI sentiment stress) and market regime (SPY/200-SMA binary) from a `MarketDataset`; emit a typed, lineage-annotated `MarketState`.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `dataset` | `MarketDataset` | DataPlane | yes | Full OHLCV/news/fundamentals for all tickers; must have `validation_status == "valid"` |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `market_state` | `MarketState` | ScoringEngine | Per-ticker `TickerFeatures` (momentum, volatility, RSI, volatility_ewma, scsi) + market `regime` for every ticker in the dataset |
| `regime` (on `MarketState`) | `str` | ScoringEngine | "EXPANSION" or "CONTRACTION"; defaults to "EXPANSION" + reason_code when SPY absent |
| `volatility_ewma` (on `TickerFeatures`) | `Decimal` | ScoringEngine | EWMA std dev of returns, span=38 (λ≈0.94); ≥ Decimal("0") |
| `scsi` (on `TickerFeatures`) | `Decimal` | ScoringEngine | Stress signal: (news_sentiment − 0.5) × ln(2); MVP article_count=1 |

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
- `market_state.reason_codes` is an empty list when regime can be computed and no RSI clamping occurs
- Monetary values: Decimal only, never float
- No external I/O; purely in-memory computation
- `regime ∈ {"EXPANSION", "CONTRACTION"}`; if SPY not in `dataset.data`, regime="EXPANSION", reason_code="regime_spy_missing"; if SPY has <200 bars, reason_code="regime_spy_insufficient_bars"
- `volatility_ewma ≥ Decimal("0")`; requires ≥ 2 bars; returns `Decimal("0")` if all returns are zero
- `scsi` per-ticker: `(ticker_data.news_sentiment − Decimal("0.5")) × Decimal("0.693147180559945")`; no clamping; article_count=1 MVP stub (documented in ADR 0003)
- `MarketState.validate()` checks `regime ∈ {"EXPANSION", "CONTRACTION"}`

### Future Work: SCSI Full Activation
Real formula: `stress_raw = (mean_sentiment − 0.5) × log(1 + article_count)`
Activation requires a sealed-node ADR (changes `TickerData` and `DataPlane` contract):
1. Add `article_count: int` to `TickerData` domain object
2. Update `_load_sentiment_for_ticker()` in `real_adapter.py` to return `(mean_sentiment, count)` tuple
3. Update `_scsi_from_sentiment(sentiment, article_count)` signature in `market_state_engine.py`
4. Update `DataPlane` contract to reflect new `TickerData` field

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| Ticker has fewer than 21 OHLCV bars (momentum/volatility) | M | H | Raises `InsufficientDataError` with ticker name and bar counts in message |
| Ticker has fewer than 15 OHLCV bars (RSI) | M | H | Raises `InsufficientDataError` with ticker name and bar counts in message |
| Division by zero in momentum (prior close == 0) | L | H | Raises `DataIntegrityError("close price is zero for ticker {ticker} at {date}")` |
| Ticker missing from `dataset.data` during iteration | L | H | Raises `KeyError(f"ticker {ticker} not found in MarketDataset")` |
| RSI computation produces value outside [0, 100] due to floating-point intermediate | L | M | Clamp to `[Decimal("0"), Decimal("100")]` after conversion; populate `reason_codes` with `"rsi_clamped:{ticker}"` |
| SPY absent from dataset (regime) | H | L | Default "EXPANSION" + reason_code "regime_spy_missing" |
| SPY has <200 bars (regime) | M | L | Default "EXPANSION" + reason_code "regime_spy_insufficient_bars" |

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
- [ ] `test_market_state_engine_volatility_ewma_is_nonneg`
- [ ] `test_market_state_engine_scsi_sign_matches_sentiment`
- [ ] `test_market_state_engine_regime_defaults_to_expansion_without_spy`

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
