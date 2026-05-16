"""Unit tests for experiment_engine.config_loader."""

import pytest

from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.experiment_engine import create_experiment_params, load_experiment_config
from portfolio_ninja.experiment_engine.config_loader import _DEFAULT_CONFIG_PATH


def test_config_loader_reads_yaml_returns_dict(tmp_path):
    cfg_file = tmp_path / "experiment_config.yaml"
    cfg_file.write_text(
        "scoring_model_id: technical_composite_v1\ntop_n: 5\nrebalance_freq: daily\n"
    )
    result = load_experiment_config(cfg_file)
    assert result == {
        "scoring_model_id": "technical_composite_v1",
        "top_n": 5,
        "rebalance_freq": "daily",
    }


def test_config_loader_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_experiment_config(tmp_path / "does_not_exist.yaml")


def test_config_loader_missing_key_raises_key_error(tmp_path):
    cfg_file = tmp_path / "experiment_config.yaml"
    cfg_file.write_text("scoring_model_id: technical_composite_v1\ntop_n: 5\n")
    with pytest.raises(KeyError, match="rebalance_freq"):
        load_experiment_config(cfg_file)


def test_config_loader_passes_values_to_create_experiment_params(tmp_path):
    cfg_file = tmp_path / "experiment_config.yaml"
    cfg_file.write_text(
        "scoring_model_id: stub_v1\ntop_n: 3\nrebalance_freq: weekly\n"
    )
    cfg = load_experiment_config(cfg_file)
    config = RunConfig(tickers=["AAPL"], run_mode="backtest", window_days=120)
    ep = create_experiment_params(
        config,
        scoring_model_id=cfg["scoring_model_id"],
        top_n=cfg["top_n"],
        rebalance_freq=cfg["rebalance_freq"],
    )
    assert ep.validation_status == "valid"
    assert ep.scoring_model_id == "stub_v1"
    assert ep.top_n == 3
    assert ep.rebalance_freq == "weekly"
    assert len(ep.params_hash) == 64


def test_config_loader_default_path_points_to_real_file():
    assert _DEFAULT_CONFIG_PATH.exists(), f"Default config missing: {_DEFAULT_CONFIG_PATH}"
    cfg = load_experiment_config()
    assert cfg["scoring_model_id"] == "technical_composite_v1"
