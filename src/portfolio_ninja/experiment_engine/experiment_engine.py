import hashlib

from portfolio_ninja.domain.objects import ExperimentParams, RunConfig

_VALID_REBALANCE_FREQS = {"daily", "weekly", "monthly"}
_DEFAULT_SCORING_MODEL_ID = "technical_composite_v1"
_DEFAULT_TOP_N = 5
_DEFAULT_REBALANCE_FREQ = "daily"

# Ported from legacy model_factory.py MODEL_REGISTRY — prevents invalid IDs reaching ScoringEngine.
_REGISTERED_SCORING_MODELS: frozenset[str] = frozenset({"stub_v1", "technical_composite_v1"})


def create_experiment_params(
    config: RunConfig,
    scoring_model_id: str = _DEFAULT_SCORING_MODEL_ID,
    top_n: int = _DEFAULT_TOP_N,
    rebalance_freq: str = _DEFAULT_REBALANCE_FREQ,
) -> ExperimentParams:
    if scoring_model_id not in _REGISTERED_SCORING_MODELS:
        raise ValueError(
            f"scoring_model_id '{scoring_model_id}' not in {sorted(_REGISTERED_SCORING_MODELS)}"
        )
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if rebalance_freq not in _VALID_REBALANCE_FREQS:
        raise ValueError(
            f"rebalance_freq '{rebalance_freq}' not in {_VALID_REBALANCE_FREQS}"
        )

    hash_input = f"{scoring_model_id}|{top_n}|{rebalance_freq}".encode()
    params_hash = hashlib.sha256(hash_input).hexdigest()

    return ExperimentParams(
        scoring_model_id=scoring_model_id,
        top_n=top_n,
        rebalance_freq=rebalance_freq,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=[],
    )
