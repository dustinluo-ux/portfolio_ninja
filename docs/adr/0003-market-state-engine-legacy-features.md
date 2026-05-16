# ADR 0003: MarketStateEngine — LEGACY Feature Integration

## Status
Accepted

## Context

The LEGACY mining audit (`LEGACY_MODULE_MAPPING.md`, `LEGACY_MIGRATION_PLAN.md`, `LEGACY_MINING_EVIDENCE.md`) identified three features explicitly planned for MarketStateEngine but never implemented:

1. **`regime: str`** — SPY/200-SMA binary market regime ("EXPANSION"|"CONTRACTION"), sourced from `src/execution/regime_controller.py` in ai_supply_chain_trading (Class B).
2. **`volatility_ewma: Decimal`** — EWMA volatility with span=38 (λ≈0.94), sourced from `pods/pod_core.py` `EWMA_SPAN = 38` (Class B).
3. **`scsi: Decimal`** — Stress Composite Signal Index from news_sentiment, sourced from `src/signals/feature_engineering.py` lines 44–48 (Class B).

`LEGACY_MIGRATION_PLAN.md` Module 3 Migration Notes state verbatim:
> "The regime binary and SCSI formula are the two core intellectual contributions of this module's legacy code. Both are simple arithmetic. Port the formulas as pure functions that accept `MarketDataset` as input and return typed feature fields on `MarketState`. The EWMA vol estimate from `pod_core.py` is a secondary feature; include it as `MarketState.volatility_ewma` for the scoring module to consume."

`MarketState` and `TickerFeatures` are cross-module interfaces (sealed-node architecture). This ADR gates the contract and domain-object changes required to add these fields.

## Decision

Add three new fields to the domain objects:

### `regime: str` on `MarketState`
- Values: `"EXPANSION"` (SPY close ≥ 200-SMA) or `"CONTRACTION"` (SPY close < 200-SMA)
- Computed by `_regime_signal(dataset)` using `dataset.data["SPY"].ohlcv`
- Graceful degradation when SPY is absent or has fewer than 200 bars: default to `"EXPANSION"` and populate `reason_codes` with `"regime_spy_missing"` or `"regime_spy_insufficient_bars"`
- Required field (not defaulted); `MarketState.validate()` enforces membership in `{"EXPANSION", "CONTRACTION"}`
- Note: Regime-adjusted scoring weights are deferred to a future ADR; this ADR gates the data field only

### `volatility_ewma: Decimal` on `TickerFeatures`
- EWMA standard deviation of daily log-returns, span=38 (α=2/39, λ=37/39)
- Formula (rewritten from pandas `ewm(span=38, adjust=False).std()` in pure Decimal):
  - returns[i] = (close[i] − close[i−1]) / close[i−1], skipping zero denominators
  - var₀ = returns[0]²
  - varᵢ = λ·varᵢ₋₁ + α·returnsᵢ²
  - volatility_ewma = sqrt(final_var), quantized to 6 decimal places
  - Returns `Decimal("0")` if fewer than 2 distinct closes or all returns are zero
- Required ≥ 2 bars; raises `InsufficientDataError` if not met
- `TickerFeatures.validate()` enforces `volatility_ewma >= Decimal("0")`

### `scsi: Decimal` on `TickerFeatures`
- Stress Composite Signal Index — sentiment-derived stress signal
- Legacy formula (`feature_engineering.py` lines 44–48): `stress_raw = (mean_sentiment − 0.5) × log(1 + article_count)`
- MVP stub: `article_count = 1` (FinBERT article count integration is out of scope)
  - Simplifies to: `scsi = (news_sentiment − 0.5) × ln(2)`
  - `_LN2 = Decimal("0.693147180559945")` (pre-computed literal)
- No clamping; value range is unbounded (typically −0.35 to +0.35 for sentiment ∈ [0, 1])
- Pure function with no external I/O

## Consequences

- 8 files updated across domain objects, implementation, tests (unit + E2E)
- ScoringEngine now receives `regime`, `volatility_ewma`, `scsi` via `MarketState`/`TickerFeatures`; the scoring model is not required to consume them immediately
- Regime-adjusted scoring weights are explicitly deferred to a future ADR (ADR 0004 candidate)
- All 6 construction sites for `TickerFeatures` in tests must add `volatility_ewma` and `scsi` fields
- All 8 construction sites for `MarketState` in tests must add `regime` field
- Zero undocumented stubs: `article_count=1` is documented here and in the function; `"EXPANSION"` fallback is documented here and via `reason_codes`

## Legacy Mining Provenance

| Asset | Legacy File | Class | Action |
|-------|-------------|-------|--------|
| SCSI formula | `src/signals/feature_engineering.py` L44–48 | B | Rewritten: article_count=1, Decimal, no pandas |
| EWMA span constant | `pods/pod_core.py` L10 | A | `EWMA_SPAN = 38` extracted directly |
| EWMA variance formula | `pods/pod_core.py` L107–108 | B | Rewritten in pure Decimal; no numpy |
| Regime constants | `src/execution/regime_controller.py` | A | BEAR_MULTIPLIER=0.6, EXPANSION_MAX_LONGS=5, CONTRACTION_MAX_LONGS=3 noted; scoring integration deferred |
| SPY/200-SMA regime logic | `src/execution/regime_controller.py` | B | Rewritten as pure function from MarketDataset; no file I/O |
