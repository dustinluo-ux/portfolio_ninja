# Contract: UniverseGateway

## Purpose
Accept an external ticker list and run configuration via `RunConfig`; validate all inputs; emit a typed, lineage-annotated `Universe` object for consumption by DataPlane.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `config` | `RunConfig` | External caller / orchestrator | yes | Contains `tickers: list[str]`, `run_mode: str`, `window_days: int`; must be fully populated before this module is invoked |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `universe` | `Universe` | DataPlane | Validated ticker list with run mode, window, as-of date, params hash, and validation lineage |

## Dependencies
- `domain` — provides `RunConfig` and `Universe` typed dataclasses; `Universe.validate()` for invariant enforcement

## Invariants
- `universe.tickers` is non-empty; raises `ValueError("tickers must not be empty")` otherwise
- `universe.run_mode` is one of `{"backtest", "paper", "live"}`; raises `ValueError` otherwise
- `universe.window_days > 0`; raises `ValueError` otherwise
- `universe.validation_status == "valid"` on successful exit
- `universe.as_of_date` is set to the current UTC date at time of call
- `universe.params_hash` is a SHA-256 hex digest of `(sorted(tickers), run_mode, window_days)`
- `universe.reason_codes` is an empty list on success
- Monetary values: Decimal only, never float
- No external I/O; purely in-memory validation

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| Empty ticker list | M | H | Raises `ValueError("tickers must not be empty")` immediately; no partial output emitted |
| Invalid `run_mode` (not in allowed set) | M | H | Raises `ValueError(f"run_mode '{run_mode}' not in {'backtest','paper','live'}")` immediately |
| `window_days <= 0` | L | M | Raises `ValueError("window_days must be > 0")` immediately |
| Duplicate tickers in list | L | L | Deduplicate deterministically (sorted unique list) and populate `reason_codes` with `"tickers_deduplicated"` |

## Tests Required
- [ ] `test_universe_gateway_valid_config_returns_valid_universe`
- [ ] `test_universe_gateway_empty_tickers_raises_value_error`
- [ ] `test_universe_gateway_invalid_run_mode_raises_value_error`
- [ ] `test_universe_gateway_window_days_zero_raises_value_error`
- [ ] `test_universe_gateway_window_days_negative_raises_value_error`
- [ ] `test_universe_gateway_duplicate_tickers_are_deduplicated_and_reason_code_set`
- [ ] `test_universe_gateway_params_hash_is_deterministic_for_same_inputs`
- [ ] `test_universe_gateway_validation_status_is_valid_on_success`

## Acceptance Criteria
- [ ] Returns `Universe` with `validation_status == "valid"` for a valid `RunConfig`
- [ ] Raises `ValueError` for empty tickers, invalid `run_mode`, and non-positive `window_days`
- [ ] `params_hash` is a non-empty SHA-256 hex string and is identical across two calls with the same inputs
- [ ] `as_of_date` is the current UTC date (testable via date injection)
- [ ] Duplicate tickers are deduplicated; `reason_codes` contains `"tickers_deduplicated"` when deduplication occurred
- [ ] No `float` anywhere in module code

## Upstream Providers
- External caller / orchestrator (supplies `RunConfig`)

## Downstream Consumers
- DataPlane (consumes `Universe`)
