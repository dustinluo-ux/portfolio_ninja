# Contract: ParamsLoader

## Purpose
Single source of truth for all tunable algorithm constants. Reads `config/params.yaml`,
validates required sections, and returns a raw dict. Caches on first call for the default path.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| path | Path \| None | caller | no | Custom YAML path; bypasses cache when provided |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| params | dict[str, Any] | scoring_engine, market_state_engine, portfolio_construction_engine, risk_engine | Nested dict keyed by module section |

## Dependencies
- `pyyaml` — YAML parsing

## Invariants
- Required top-level sections: `market_state`, `scoring`, `portfolio`, `risk`, `data`, `date_normalizer`
- Decimal-compatible values are stored as quoted strings in the YAML to prevent float precision loss
- Cache is populated only for the default path; custom paths bypass cache
- Module-level constants derived from params must match `config/params.yaml` defaults exactly

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| params.yaml missing from repo | L | H | FileNotFoundError raised at import time of any dependent module |
| Required section missing | L | H | KeyError raised with section name list |
| YAML is not a mapping | L | M | ValueError raised with type name |

## Tests Required
- [x] `test_params_loader_default_path_returns_dict`
- [x] `test_params_loader_has_all_required_sections`
- [x] `test_params_loader_scoring_weights_sum_to_one`
- [x] `test_params_loader_market_state_periods_are_positive_ints`
- [x] `test_params_loader_default_is_cached`
- [x] `test_params_loader_missing_file_raises`
- [x] `test_params_loader_missing_section_raises`
- [x] `test_params_loader_non_mapping_yaml_raises`
- [x] `test_params_loader_custom_path_reads_correct_values`
- [x] `test_params_loader_custom_path_does_not_pollute_default_cache`

## Acceptance Criteria
- [x] `load_params()` returns correct defaults matching prior hardcoded values
- [x] Changing `params.yaml` changes module behavior without source edits
- [x] Custom path supported for test isolation

## Upstream Providers
- `config/params.yaml` — filesystem

## Downstream Consumers
- `scoring_engine.py` — scoring weights + degenerate score
- `market_state_engine.py` — indicator periods + EWMA span + SCSI baseline
- `portfolio_construction_engine.py` — max_longs per regime
- `risk_engine.py` — concentration limit
