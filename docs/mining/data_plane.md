# Mining Index: DataPlane

**Source module:** `ai_supply_chain_trading/src/data/`
**Date mined:** 2026-05-14
**Status:** Complete

## Ported Assets (Class A)

| Legacy Asset | File | Destination | Notes |
|-------------|------|-------------|-------|
| `DataQualityReport` dataclass | `data_quality.py` | `domain/objects.py` | `__post_init__` → `@property` for `can_rebalance` |
| `IncompleteDataError` exception | `data_quality.py` | `domain/exceptions.py` | Verbatim port |
| `CRITICAL_SOURCES` constant | `data_quality.py` | `domain/objects.py` | Verbatim: `["prices", "smh_benchmark", "regime_status"]` |
| `DEGRADED_SOURCES` constant | `data_quality.py` | `domain/objects.py` | Verbatim: `["eodhd_news", "tiingo_news", "marketaux_news", "meta_weights"]` |
| `SourceCriticality` enum | new | `domain/objects.py` | Type-safe wrapper for source criticality labels |

## Decimal Cast Pattern (Reference)

Legacy `_cast_ohlc_to_decimal()` in `resilience_layer.py` converts pandas DataFrame OHLC columns to Decimal:

```python
# Legacy pattern (pandas-dependent, DO NOT COPY):
out[col] = out[col].map(lambda x: Decimal(str(float(x))) if pd.notna(x) else Decimal("NaN"))
```

Portfolio_ninja translation: use `Decimal(str(value))` at construction time in real adapters. The existing `StubDataAdapter` already follows this pattern for every OHLCV field.

Future real adapters must ensure every `OHLCVBar.open/high/low/close` is `Decimal` before constructing the dataclass.

## Rejected Assets

### Class C (Rewrite Required — Not Ported)

| Asset | File | Contamination Risk | Reason |
|-------|------|-------------------|--------|
| `BaseDataProvider.get_current_price()` | `base_provider.py` | CR-003 | Returns `float` not `Decimal`; new `DataAdapter.fetch()` supersedes |
| `CSVDataProvider.load_prices()` | `csv_provider.py` | CR-005 | print-not-raise on missing file; returns empty dict silently |
| `DataProviderFactory.from_config_file()` | `provider_factory.py` | CR-004 | Bare `except Exception` silent fallback to CSV |
| `news_fetcher_factory.py` | `news_fetcher_factory.py` | CR-007 | Hardcoded `C:/ai_supply_chain_trading/...` fallback path |

### Class D (Ignore — Not Ported)

| Asset | File | Reason |
|-------|------|--------|
| `download_fundamentals.py` | `scripts/` | Batch download script, not a runtime module |
| `fmp_ingest.py` | `src/data/` | FMP-specific paid API, not approved for MVP |
| `edgar_audit.py` | `src/data/` | SEC scraping, separate concern |

## Class B (Idea — Deferred)

| Concept | File | Status |
|---------|------|--------|
| VendorEvent telemetry | `state.py` | Deferred to AuditMonitor mining pass |
| `_run_vendor` timing wrapper | `resilience_layer.py` | Deferred to AuditMonitor mining pass |
| `_slice_date_range` utility | `resilience_layer.py` | Deferred to real adapter implementation |

## Contamination Risks Applied

| Risk ID | Severity | Applied To |
|---------|----------|-----------|
| CR-003 | HIGH | `base_provider.py` — float return type |
| CR-004 | HIGH | `provider_factory.py` — silent CSV fallback |
| CR-005 | HIGH | `csv_provider.py` — print-not-raise |
| CR-006 | HIGH | `resilience_layer.py` — bare excepts (structure not ported) |
| CR-007 | HIGH | `news_fetcher_factory.py` — hardcoded paths |
| CR-008 | HIGH | Multiple config files — config drift |

## Future Needs

When replacing `StubDataAdapter` with a real adapter:

1. **Vendor fallback chain** (`resilience_layer.py`): CSV → Marketaux → YFinance pattern is structurally sound. Must replace bare excepts with typed catches.
2. **Telemetry** (`resilience_layer.py` `_run_vendor`): Vendor event logging with timing should integrate with `AuditMonitor` VendorEvent model.
3. **Date slicing** (`resilience_layer.py` `_slice_date_range`): Reimplement with standard `datetime.date` comparisons, not pandas.
