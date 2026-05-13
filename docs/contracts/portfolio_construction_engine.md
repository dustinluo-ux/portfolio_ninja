# Contract: PortfolioConstructionEngine

## Purpose
Construct equal-weight target portfolio weights from the top-N tickers in `RankedUniverse` using `ExperimentParams.top_n`; emit a typed, lineage-annotated `TargetPortfolio` whose weights sum exactly to `Decimal("1.0")`.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `ranked_universe` | `RankedUniverse` | ScoreArbitrationEngine | yes | All tickers sorted descending by score; must have `validation_status == "valid"` and at least one entry |
| `experiment_params` | `ExperimentParams` | ExperimentEngine (side-input) | yes | `top_n` controls how many tickers are selected; must have `validation_status == "valid"` |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `target_portfolio` | `TargetPortfolio` | RiskEngine | Equal-weight allocation across selected tickers; weights sum exactly to `Decimal("1.0")` |

## Dependencies
- `domain` — provides `RankedUniverse`, `ExperimentParams`, `TargetPortfolio` types
- `ScoreArbitrationEngine` — must have approved contract; provides `RankedUniverse`
- `ExperimentEngine` — must have approved contract; provides `ExperimentParams`

## Invariants
- `target_portfolio.weights` contains exactly `min(experiment_params.top_n, len(ranked_universe.ranked))` tickers
- If `len(ranked_universe.ranked) < experiment_params.top_n`, all ranked tickers are selected (no error; `reason_codes` populated with `"top_n_capped:{actual}"`
- Weight per ticker = `Decimal("1") / Decimal(str(n))` where `n` is the number of selected tickers
- `sum(target_portfolio.weights.values()) == Decimal("1.0")` exactly; enforced by `validate()` raising `WeightSumError` otherwise
- Empty `ranked_universe.ranked` raises `ValueError("RankedUniverse must not be empty")`
- `experiment_params.top_n <= 0` raises `ValueError("top_n must be >= 1")` (validated by ExperimentEngine, re-checked here as defensive assertion)
- All weight values are `decimal.Decimal`; never `float`
- `target_portfolio.validation_status == "valid"` on successful exit
- `target_portfolio.as_of_date == ranked_universe.as_of_date`
- `target_portfolio.params_hash` is SHA-256 hex of `(ranked_universe.params_hash, experiment_params.params_hash)`
- `target_portfolio.reason_codes` is an empty list on success (or `["top_n_capped:{actual}"]` if capped)
- Monetary values: Decimal only, never float
- No external I/O; purely in-memory computation

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| Empty `ranked_universe.ranked` | L | H | Raises `ValueError("RankedUniverse must not be empty")` |
| `experiment_params.top_n <= 0` | L | H | Raises `ValueError("top_n must be >= 1")` |
| `len(ranked) < top_n` | M | L | Selects all available tickers; populates `reason_codes` with `"top_n_capped:{actual}"`; no error |
| Weight sum != `Decimal("1.0")` due to Decimal division rounding | L | H | Allocate residual (`Decimal("1.0") - sum(calculated_weights)`) to the first ticker; ensures exact sum |

## Tests Required
- [ ] `test_portfolio_construction_engine_valid_inputs_returns_target_portfolio`
- [ ] `test_portfolio_construction_engine_weights_are_equal_for_all_selected_tickers`
- [ ] `test_portfolio_construction_engine_weights_sum_exactly_to_one`
- [ ] `test_portfolio_construction_engine_top_n_greater_than_available_selects_all`
- [ ] `test_portfolio_construction_engine_empty_ranked_universe_raises_value_error`
- [ ] `test_portfolio_construction_engine_top_n_zero_raises_value_error`
- [ ] `test_portfolio_construction_engine_all_weights_are_decimal`
- [ ] `test_portfolio_construction_engine_validation_status_is_valid_on_success`
- [ ] `test_portfolio_construction_engine_top_n_capped_populates_reason_codes`

## Acceptance Criteria
- [ ] Returns `TargetPortfolio` with exactly `min(top_n, len(ranked))` tickers
- [ ] All weights are equal (`Decimal("1") / Decimal(str(n))`) and sum exactly to `Decimal("1.0")`
- [ ] Raises `ValueError` for empty `ranked_universe` or `top_n <= 0`
- [ ] When `len(ranked) < top_n`, all tickers are selected and `reason_codes` reflects the cap
- [ ] All weight values are `Decimal`; no `float` anywhere in module code
- [ ] `validation_status == "valid"` on success

## Upstream Providers
- ScoreArbitrationEngine (provides `RankedUniverse`)
- ExperimentEngine (provides `ExperimentParams` as side-input)

## Downstream Consumers
- RiskEngine (consumes `TargetPortfolio`)
