# ADR 0005: PortfolioConstructionEngine — Regime-Aware Max Longs

## Status
Accepted

## Context

`LEGACY_MINING_EVIDENCE.md` and `src/execution/regime_controller.py` in ai_supply_chain_trading define:
- `EXPANSION_MAX_LONGS = 5`
- `CONTRACTION_MAX_LONGS = 3`

In CONTRACTION, the legacy system caps the portfolio at 3 long positions (risk-off posture). In EXPANSION, up to 5 longs are allowed.

`PortfolioConstructionEngine` currently uses `n = min(experiment_params.top_n, available)` with no regime awareness — it always allows up to `top_n` positions regardless of market regime.

## Decision

Add `regime: str = "EXPANSION"` as an optional parameter to `construct_portfolio()`.

```python
max_longs = 3 if regime == "CONTRACTION" else 5
n = min(experiment_params.top_n, max_longs, available)
```

- Default `"EXPANSION"` preserves backward compatibility for all existing tests.
- The orchestrator passes `market_state.regime` as the third argument.
- No scoring formula changes — weights (momentum 40%, inverted-volatility 30%, RSI 30%) remain unchanged.
- `max_longs` caps are sourced from `regime_controller.py` constants; treating as Class A (extracted directly).

## Consequences

- All existing `construct_portfolio(ru, ep)` call sites continue to work (default `"EXPANSION"` → `max_longs=5`).
- Existing tests with `top_n=3` or fewer are unaffected: `min(3, 5, available)` = `min(3, available)` = same result.
- New tests added: CONTRACTION mode caps at 3; EXPANSION mode caps at 5.
- Orchestrator updated to pass `market_state.regime` — no contract change required (optional param).
- Contract `portfolio_construction_engine.md` updated to document the `regime` parameter and `max_longs` invariants.
- 3 files changed: `portfolio_construction_engine.py`, `orchestrator.py`, `tests/test_portfolio_construction_engine.py`.
