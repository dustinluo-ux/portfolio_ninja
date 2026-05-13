# Contract: ScoreArbitrationEngine

## Purpose
Rank all tickers by their score from `ScoreSet`; resolve ties deterministically via lexicographic ascending order; emit a typed, lineage-annotated `RankedUniverse`.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `score_set` | `ScoreSet` | ScoringEngine | yes | `Decimal` scores for all tickers; must have `validation_status == "valid"` and at least one entry |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `ranked_universe` | `RankedUniverse` | PortfolioConstructionEngine | All tickers from `score_set.scores` sorted descending by score; ties broken by ascending ticker string |

## Dependencies
- `domain` — provides `ScoreSet` and `RankedUniverse` types
- `ScoringEngine` — must have approved contract; provides `ScoreSet`

## Invariants
- `ranked_universe.ranked` contains every ticker from `score_set.scores`; no ticker is added or dropped
- `ranked_universe.ranked` is sorted descending by score (`Decimal` comparison)
- Ties in score are broken by ascending lexicographic order of the ticker string (deterministic)
- All score values in `ranked_universe.ranked` are `decimal.Decimal`
- Empty `score_set.scores` raises `ValueError("ScoreSet must not be empty")`
- `ranked_universe.validation_status == "valid"` on successful exit
- `ranked_universe.as_of_date == score_set.as_of_date`
- `ranked_universe.params_hash` is SHA-256 hex of `(score_set.params_hash, "score_arbitration_engine_v1")`
- `ranked_universe.reason_codes` is an empty list on success
- Monetary values: Decimal only, never float
- No external I/O; purely in-memory sort

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| Empty `score_set.scores` | L | H | Raises `ValueError("ScoreSet must not be empty")` immediately |
| Non-deterministic sort (float comparison, NaN) | L | H | All scores are `Decimal`; sort key is `(-score, ticker)` tuple; fully deterministic |

## Tests Required
- [ ] `test_score_arbitration_engine_valid_scores_returns_ranked_universe`
- [ ] `test_score_arbitration_engine_ranked_list_contains_every_ticker`
- [ ] `test_score_arbitration_engine_ranked_descending_by_score`
- [ ] `test_score_arbitration_engine_tie_breaking_is_lexicographic_ascending`
- [ ] `test_score_arbitration_engine_empty_score_set_raises_value_error`
- [ ] `test_score_arbitration_engine_all_scores_in_output_are_decimal`
- [ ] `test_score_arbitration_engine_validation_status_is_valid_on_success`
- [ ] `test_score_arbitration_engine_params_hash_is_deterministic`

## Acceptance Criteria
- [ ] Returns `RankedUniverse` with all tickers from `score_set.scores` in descending score order
- [ ] Ties are broken by ascending ticker string (verified by test with two equal-score tickers)
- [ ] Raises `ValueError` for empty `score_set.scores`
- [ ] All score values in `ranked_universe.ranked` are `Decimal`
- [ ] `validation_status == "valid"` on success
- [ ] No `float` anywhere in module code

## Upstream Providers
- ScoringEngine (provides `ScoreSet`)

## Downstream Consumers
- PortfolioConstructionEngine (consumes `RankedUniverse`)
