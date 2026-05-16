# Contract: ExperimentEngine

## Purpose
Construct a typed `ExperimentParams` object from `RunConfig`; define the scoring model identifier, top-N selection count, and rebalance frequency to be used for the current pipeline run.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `config` | `RunConfig` | External caller / orchestrator | yes | Contains `tickers`, `run_mode`, `window_days`; ExperimentEngine reads run-level config to derive experiment parameters |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `experiment_params` | `ExperimentParams` | ScoringEngine, PortfolioConstructionEngine (both via side-input) | Fully validated experiment configuration including scoring model ID, top-N, rebalance frequency, and params hash |

## Dependencies
- `domain` — provides `RunConfig` and `ExperimentParams` typed dataclasses

## Invariants
- `experiment_params.scoring_model_id` is a member of `_REGISTERED_SCORING_MODELS`; raises `ValueError` otherwise
- `experiment_params.top_n >= 1`; raises `ValueError("top_n must be >= 1")` otherwise
- `experiment_params.rebalance_freq` is one of `{"daily", "weekly", "monthly"}`; raises `ValueError` otherwise
- `experiment_params.params_hash` is a SHA-256 hex digest of `(scoring_model_id, str(top_n), rebalance_freq)`
- `experiment_params.validation_status == "valid"` on successful exit
- `experiment_params.reason_codes` is an empty list on success
- Default values: `scoring_model_id = "technical_composite_v1"`, `top_n = 5`, `rebalance_freq = "daily"` (from `config/experiment_config.yaml`)
- Monetary values: Decimal only, never float
- No external I/O; purely in-memory construction

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| `top_n < 1` (including 0 or negative) | L | H | Raises `ValueError("top_n must be >= 1")` immediately |
| Invalid `rebalance_freq` | L | M | Raises `ValueError(f"rebalance_freq '{val}' not in {'daily','weekly','monthly'}")` |
| Unregistered `scoring_model_id` | L | H | Raises `ValueError` listing valid IDs from `_REGISTERED_SCORING_MODELS` |

## Tests Required
- [ ] `test_experiment_engine_valid_config_returns_valid_experiment_params`
- [ ] `test_experiment_engine_top_n_zero_raises_value_error`
- [ ] `test_experiment_engine_top_n_negative_raises_value_error`
- [ ] `test_experiment_engine_invalid_rebalance_freq_raises_value_error`
- [ ] `test_experiment_engine_params_hash_is_deterministic_for_same_inputs`
- [ ] `test_experiment_engine_validation_status_is_valid_on_success`
- [ ] `test_experiment_engine_scoring_model_id_is_propagated_correctly`

## Acceptance Criteria
- [ ] Returns `ExperimentParams` with `validation_status == "valid"` for valid config
- [ ] Raises `ValueError` when `top_n < 1` or `rebalance_freq` is not in the allowed set
- [ ] `params_hash` is a non-empty SHA-256 hex string identical across two calls with same inputs
- [ ] `scoring_model_id` defaults to `"technical_composite_v1"` (from `config/experiment_config.yaml`)
- [ ] No `float` anywhere in module code

## Upstream Providers
- External caller / orchestrator (supplies `RunConfig`)
- ExperimentConfigLoader (optional; orchestrator reads `config/experiment_config.yaml` before calling `create_experiment_params`; the engine itself has no I/O)

## Downstream Consumers
- ScoringEngine (consumes `ExperimentParams` as side-input)
- PortfolioConstructionEngine (consumes `ExperimentParams` as side-input)
