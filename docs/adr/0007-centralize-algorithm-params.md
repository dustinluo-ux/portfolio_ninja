# ADR 0007 — Centralize Algorithm Parameters in config/params.yaml

## Status
Accepted

## Context
~45 numeric constants controlling algorithm behavior (scoring weights, indicator periods,
regime thresholds, position limits) are hardcoded in 4 sealed-node modules:
`scoring_engine.py`, `market_state_engine.py`, `portfolio_construction_engine.py`,
`risk_engine.py`. Changing any parameter requires editing source code; running optimization
sweeps requires patching and restoring files.

The existing `config/experiment_config.yaml` proves the pattern works for experiment-level
knobs. Extending it to algorithm parameters creates a single entry point for all tunable values.

## Decision
1. Create `config/params.yaml` containing all algorithm-affecting constants, grouped by module section.
2. Create `src/portfolio_ninja/config/params_loader.py` exposing `load_params()` — reads the
   YAML, validates required sections, returns a `dict`. Caches on first call for the default path.
3. Update the 4 affected modules to load their constants from `load_params()` at module init
   time. Cross-node contracts (input/output types, function signatures) are unchanged.

Operational parameters (API timeouts, rate-limit delays, pagination limits) are excluded —
they do not affect model output and are not optimization candidates (Phase 1 scope).

## Consequences
**Positive:**
- Single file to edit when tuning or running optimization sweeps.
- params_hash in each domain object already captures which values produced a given result;
  changing `params.yaml` implicitly changes those hashes, preserving lineage.
- No sealed-node interface contract changes (inputs/outputs/types unchanged).

**Negative:**
- Modules now depend on the filesystem at import time; tests that patch constants must
  supply a custom `params.yaml` path via `load_params(path=...)`.
- `params.yaml` must be kept in sync when adding new constants.

## Sealed-Node Gate
Cross-node contracts are unchanged. This ADR covers intra-node constant extraction only.
No downstream consumer interface is affected.
