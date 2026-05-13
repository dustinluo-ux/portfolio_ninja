# Contract: DataPlane

## Purpose
Fetch market data (OHLCV bars, news sentiment, fundamentals) for all tickers in a validated `Universe` via the injected `DataAdapter`; emit a typed, lineage-annotated `MarketDataset`.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `universe` | `Universe` | UniverseGateway | yes | Validated ticker list with run mode, window days, and as-of date |
| `adapter` | `DataAdapter` | Orchestrator (dependency injection) | yes | Concrete implementation of `DataAdapter` ABC; in MVP this is `StubDataAdapter` |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `dataset` | `MarketDataset` | MarketStateEngine | Full OHLCV/news/fundamentals data for every ticker in `universe.tickers`; includes `source_data_version` and full lineage |

## Dependencies
- `domain` — provides `Universe`, `MarketDataset`, `TickerData`, `OHLCVBar`, and `DataAdapter` types
- `UniverseGateway` — must have approved contract; provides `Universe` input

## Invariants
- `dataset.data` has an entry for every ticker in `universe.tickers`; raises `DataUnavailableError` if any ticker is missing from the adapter response
- `dataset.source_data_version` is non-empty string; populated from adapter response metadata
- All price fields (`OHLCVBar.open`, `.high`, `.low`, `.close`) and sentiment/fundamental fields (`TickerData.news_sentiment`, `TickerData.pe_ratio`) are `decimal.Decimal`; never `float`
- `OHLCVBar.high >= OHLCVBar.low` for every bar; raises `DataIntegrityError` on violation
- `OHLCVBar.volume >= 0` for every bar
- `dataset.validation_status == "valid"` on successful exit
- `dataset.as_of_date == universe.as_of_date`
- `dataset.params_hash` is SHA-256 hex of `(universe.params_hash, source_data_version)`
- `dataset.reason_codes` is an empty list on success
- Monetary values: Decimal only, never float
- No fallback to default data on adapter failure; fail-loud

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| `DataAdapter.fetch()` raises any exception | M | H | Catches and re-raises as `DataUnavailableError` with original message; no silent fallback |
| Adapter response missing one or more tickers from `universe.tickers` | M | H | Raises `DataUnavailableError(f"Missing tickers: {missing}")` listing all absent tickers |
| Adapter returns `float` price data | L | H | Cast to `Decimal` using `Decimal(str(value))`; populate `reason_codes` with `"prices_cast_from_float"` |
| `OHLCVBar.high < OHLCVBar.low` in adapter response | L | M | Raises `DataIntegrityError` with ticker and bar date in message |
| Empty OHLCV list for a ticker | M | M | Raises `DataUnavailableError(f"Empty OHLCV for ticker {ticker}")` |

## Tests Required
- [ ] `test_data_plane_valid_universe_returns_complete_market_dataset`
- [ ] `test_data_plane_stub_adapter_produces_entry_for_every_ticker`
- [ ] `test_data_plane_missing_ticker_in_adapter_response_raises_data_unavailable_error`
- [ ] `test_data_plane_adapter_exception_propagates_as_data_unavailable_error`
- [ ] `test_data_plane_all_price_fields_are_decimal`
- [ ] `test_data_plane_source_data_version_is_non_empty`
- [ ] `test_data_plane_validation_status_is_valid_on_success`
- [ ] `test_data_plane_integration_stub_adapter_deterministic_for_same_inputs`

## Acceptance Criteria
- [ ] Returns `MarketDataset` with an entry for every ticker in `universe.tickers`
- [ ] `validation_status == "valid"` and `source_data_version` is non-empty on success
- [ ] Raises `DataUnavailableError` when adapter raises or returns incomplete data
- [ ] All price and financial fields are `decimal.Decimal`; no `float` in output
- [ ] `dataset.as_of_date == universe.as_of_date`
- [ ] Integration test with `StubDataAdapter` confirms deterministic output for identical `Universe` inputs

## Upstream Providers
- UniverseGateway (provides `Universe`)
- Orchestrator (injects `DataAdapter` implementation)

## Downstream Consumers
- MarketStateEngine (consumes `MarketDataset`)
