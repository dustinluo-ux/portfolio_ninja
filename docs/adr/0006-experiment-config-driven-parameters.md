# ADR 0006: ExperimentEngine — Config-Driven Parameters

## Status
Accepted

## Context

`ExperimentEngine` (`src/portfolio_ninja/experiment_engine/experiment_engine.py`) is a pure in-memory function that constructs `ExperimentParams`. Its default `scoring_model_id = "stub_v1"` is a stub that was never replaced after `technical_composite_v1` was fully implemented in `ScoringEngine`.

Three gaps block the "real implementation end-to-end" milestone:
1. `_DEFAULT_SCORING_MODEL_ID = "stub_v1"` — stub is the default everywhere, including `orchestrator.run()`.
2. No `config/experiment_config.yaml` exists — experiment parameters have no persisted source file.
3. No `scripts/run_pipeline.py` — the full 11-module pipeline has no production CLI entrypoint.

Legacy mining (`LEGACY_MINING_EVIDENCE.md` Candidate 9, `model_factory.py` lines 1–69) identified two Class A reuse patterns:
- `MODEL_REGISTRY` dict — enforces that only known model IDs pass through. Ported as `_REGISTERED_SCORING_MODELS` frozenset.
- `get_best_model(model_dir: Path)` — reads a YAML config and returns structured params. Ported as `load_experiment_config(config_path: Path)`.

## Decision

1. Add `_REGISTERED_SCORING_MODELS: frozenset[str] = frozenset({"stub_v1", "technical_composite_v1"})` to `experiment_engine.py`. Replace the empty-string guard with a registry membership check.

2. Create `config/experiment_config.yaml` as the persisted source of experiment defaults:
   ```yaml
   scoring_model_id: technical_composite_v1
   top_n: 5
   rebalance_freq: daily
   ```

3. Create `src/portfolio_ninja/experiment_engine/config_loader.py` with `load_experiment_config(config_path)` — the only I/O point. `ExperimentEngine` itself never calls it (contract invariant: no external I/O preserved).

4. Update `orchestrator.run()` to accept `config_path: Optional[Path] = None`. When `scoring_model_id` is not explicitly supplied, the orchestrator loads from the config file and uses it as the default. Explicit caller arguments still override config.

5. Change `_DEFAULT_SCORING_MODEL_ID = "stub_v1"` → `"technical_composite_v1"` in `experiment_engine.py`.

## Consequences

- `stub_v1` remains a valid registered model ID and continues to work as an explicit argument. All existing E2E tests that pass `scoring_model_id` explicitly are unaffected.
- The orchestrator signature gains one optional `config_path` parameter — backward-compatible.
- All tests that relied on the `stub_v1` default must be updated to `technical_composite_v1` or pass `scoring_model_id="stub_v1"` explicitly.
- `scripts/run_pipeline.py` provides end-to-end runtime evidence using real CSV data + real config.
- 5 files changed + 3 new test files + 1 new script.
