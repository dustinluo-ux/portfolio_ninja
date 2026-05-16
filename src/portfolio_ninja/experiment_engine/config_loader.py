from pathlib import Path

import yaml

_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "experiment_config.yaml"
)
_REQUIRED_KEYS = {"scoring_model_id", "top_n", "rebalance_freq"}


def load_experiment_config(config_path: Path = _DEFAULT_CONFIG_PATH) -> dict:
    """Read experiment_config.yaml; validate required keys; return raw dict.

    Raises FileNotFoundError if path is missing.
    Raises KeyError if any required key is absent.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Experiment config not found: {config_path}")
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        raise KeyError(f"experiment_config.yaml missing required keys: {sorted(missing)}")
    return data
