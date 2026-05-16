# ADR 0002: Technical Composite Scoring Model (technical_composite_v1)

**Status:** Accepted
**Date:** 2026-05-16

## Context

ScoringEngine `stub_v1` produces scores via `abs(hash(ticker)) % 1000 / 1000` — a deterministic but
arbitrary mapping from ticker strings to scores. No market signal is incorporated. Portfolio
decisions derived from these scores are meaningless for any real evaluation.

MarketStateEngine already computes three real factor signals for every ticker from actual OHLCV data:
- `momentum_20d`: 20-day price momentum (return from t-21 to t)
- `volatility_20d`: 20-day rolling annualized volatility of daily returns
- `rsi_14`: 14-day relative strength index (0–100)

These signals are proven correct (213/213 unit tests pass, 89.25% coverage), stored in `TickerFeatures`
domain objects, and already flow into `MarketState.features`. No additional data acquisition is
required to use them in scoring.

ScoringEngine interface is sealed: `(MarketState, ExperimentParams) → ScoreSet`. This ADR authorizes
an extension (new `model_id`) within the existing interface — the interface itself is unchanged.

## Decision

Add a new model_id `technical_composite_v1` to ScoringEngine.

**Algorithm:**
1. Extract `(momentum_20d, volatility_20d, rsi_14)` for all tickers from `MarketState.features`
2. Cross-sectional min-max normalize each factor independently across all tickers in the run:
   - `norm = (v − min) / (max − min)` when `max > min`; `0.5` for all tickers when all values are equal
3. Composite score: `score[ticker] = 0.4 × norm_momentum + 0.3 × (1 − norm_vol) + 0.3 × norm_rsi`
   - Inverted volatility: lower vol = higher score contribution
4. Clamp result to `[Decimal("0"), Decimal("1")]`
5. All arithmetic in `decimal.Decimal`; no `float` in computation path

**Weights rationale:** 40/30/30 — momentum leads because it is the strongest single predictor in
equity cross-sections (Jegadeesh & Titman 1993, extensively reproduced); inverted volatility rewards
risk-adjusted returns; RSI provides mean-reversion signal to complement momentum.

**Normalization:** Per-run min-max (not rolling 252-day) — no historical context is available at score
time, and per-run normalization ensures scores are always in [0,1] regardless of absolute factor levels.

**Code mine:** Cross-sectional min-max pattern recycled from
`ai_supply_chain_trading/src/signals/technical_library.py`; weighted factor blend adapted from
`ai_supply_chain_trading/src/signals/signal_engine.py`.

**Backward compatibility:** `stub_v1` remains registered and unchanged. Existing tests and the
orchestrator's default `scoring_model_id="stub_v1"` are unaffected.

## Consequences

**Positive:**
- Portfolio decisions become factor-driven rather than random; runtime validation is meaningful
- No new data dependencies — uses existing `MarketState.features` already computed
- ScoringEngine interface unchanged; sealed-node architecture preserved
- Per-run normalization ensures comparable score distributions across different market regimes

**Negative:**
- Min-max normalization is sensitive to outliers: a single extreme ticker shifts all other scores
- 40/30/30 weights are not empirically optimized for this universe; they are a reasonable prior
- Per-run normalization means a single-ticker universe always gets score `0.5` for all normalized factors

**Risks:**
- If `MarketState.features` has only one ticker, all normalized factors collapse to 0.5 and
  scores degenerate — mitigation: `_minmax_normalize` returns `[Decimal("0.5")] * len(values)`
  when `max == min`, which is the correct behavior
- Future model upgrades (ML-based) will require a new ADR and new model_id; the dispatch pattern
  in `score_tickers()` supports this without interface changes
