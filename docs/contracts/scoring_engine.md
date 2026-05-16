# Contract: ScoringEngine

## Purpose
Score each ticker in `MarketState` using the model identified in `ExperimentParams`; emit a typed, lineage-annotated `ScoreSet` where every score is a `Decimal` in `[0, 1]`.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `market_state` | `MarketState` | MarketStateEngine | yes | Per-ticker features; must have `validation_status == "valid"` |
| `experiment_params` | `ExperimentParams` | ExperimentEngine (side-input) | yes | Identifies scoring model and experiment configuration |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `score_set` | `ScoreSet` | ScoreArbitrationEngine | `Decimal` score for every ticker in `market_state.features`; model identity propagated |

## Dependencies
- `domain` — provides `MarketState`, `ExperimentParams`, `ScoreSet` types
- `MarketStateEngine` — must have approved contract; provides `MarketState`
- `ExperimentEngine` — must have approved contract; provides `ExperimentParams`

## Invariants
- `score_set.scores` has an entry for every ticker in `market_state.features`; raises `KeyError` if a feature is missing during scoring
- All score values are `decimal.Decimal` in range `[Decimal("0"), Decimal("1")]`; raises `ValueError` if any score falls outside this range
- `score_set.model_id == experiment_params.scoring_model_id`
- Registered model IDs: `{"stub_v1", "technical_composite_v1"}`
- `stub_v1` scoring formula: `score = Decimal(str(abs(hash(ticker)) % 1000)) / Decimal("1000")`; deterministic per ticker string
- `technical_composite_v1` scoring formula:
    1. Extract `(momentum_20d, volatility_20d, rsi_14)` for all tickers from `market_state.features`
    2. Cross-sectional min-max normalize each factor independently across all tickers in the run:
       `norm = (v − min) / (max − min)` when `max > min`; `Decimal("0.5")` for all when `max == min`
    3. `score[ticker] = 0.4 × norm_momentum + 0.3 × (1 − norm_volatility) + 0.3 × (norm_rsi_14 / 100)`
    4. Clamp result to `[Decimal("0"), Decimal("1")]`
    5. All arithmetic in `decimal.Decimal`; no `float` in computation path
- `score_set.validation_status == "valid"` on successful exit
- `score_set.as_of_date == market_state.as_of_date`
- `score_set.params_hash` is SHA-256 hex of `(market_state.params_hash, experiment_params.params_hash)`
- `score_set.reason_codes` is an empty list on success
- Monetary values: Decimal only, never float
- No external I/O; purely in-memory computation
- Unknown `scoring_model_id` raises `UnknownModelError` immediately; no silent fallback to stub

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| `experiment_params.scoring_model_id` not registered in model registry | L | H | Raises `UnknownModelError(f"Unknown model: {model_id}")` immediately |
| Ticker in `market_state.features` missing expected feature key during scoring | L | H | Raises `KeyError(f"Feature missing for ticker {ticker}")` |
| Computed score outside `[0, 1]` (future real model) | L | H | Raises `ValueError(f"Score out of range for ticker {ticker}: {score}")` |

## Tests Required
- [ ] `test_scoring_engine_valid_inputs_returns_complete_score_set`
- [ ] `test_scoring_engine_model_id_propagated_from_experiment_params`
- [ ] `test_scoring_engine_all_scores_are_decimal_in_zero_to_one_range`
- [ ] `test_scoring_engine_unknown_model_id_raises_unknown_model_error`
- [ ] `test_scoring_engine_scores_has_entry_for_every_ticker_in_market_state`
- [ ] `test_scoring_engine_stub_score_is_deterministic_for_same_ticker`
- [ ] `test_scoring_engine_validation_status_is_valid_on_success`
- [ ] `test_scoring_engine_params_hash_is_deterministic`

## Acceptance Criteria
- [ ] Returns `ScoreSet` with an entry for every ticker in `market_state.features`
- [ ] All score values are `Decimal` in `[Decimal("0"), Decimal("1")]`
- [ ] `score_set.model_id == experiment_params.scoring_model_id`
- [ ] `validation_status == "valid"` on success
- [ ] Raises `UnknownModelError` for unrecognized `scoring_model_id`
- [ ] No `float` anywhere in module code

## Upstream Providers
- MarketStateEngine (provides `MarketState`)
- ExperimentEngine (provides `ExperimentParams` as side-input)

## Downstream Consumers
- ScoreArbitrationEngine (consumes `ScoreSet`)
