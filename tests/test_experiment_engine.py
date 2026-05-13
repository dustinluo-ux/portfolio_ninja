import pytest

from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.experiment_engine import create_experiment_params

VALID_CONFIG = RunConfig(tickers=["AAPL", "MSFT"], run_mode="backtest", window_days=730)


def test_experiment_engine_valid_config_returns_valid_experiment_params():
    ep = create_experiment_params(VALID_CONFIG)
    assert ep.validation_status == "valid"
    assert ep.scoring_model_id == "stub_v1"
    assert ep.top_n == 5
    assert ep.rebalance_freq == "daily"
    assert len(ep.params_hash) == 64
    assert ep.reason_codes == []


def test_experiment_engine_top_n_zero_raises_value_error():
    with pytest.raises(ValueError, match="top_n must be >= 1"):
        create_experiment_params(VALID_CONFIG, top_n=0)


def test_experiment_engine_top_n_negative_raises_value_error():
    with pytest.raises(ValueError, match="top_n must be >= 1"):
        create_experiment_params(VALID_CONFIG, top_n=-1)


def test_experiment_engine_invalid_rebalance_freq_raises_value_error():
    with pytest.raises(ValueError, match="rebalance_freq"):
        create_experiment_params(VALID_CONFIG, rebalance_freq="hourly")


def test_experiment_engine_params_hash_is_deterministic_for_same_inputs():
    ep1 = create_experiment_params(VALID_CONFIG)
    ep2 = create_experiment_params(VALID_CONFIG)
    assert ep1.params_hash == ep2.params_hash


def test_experiment_engine_validation_status_is_valid_on_success():
    ep = create_experiment_params(VALID_CONFIG)
    assert ep.validation_status == "valid"


def test_experiment_engine_scoring_model_id_is_propagated_correctly():
    ep = create_experiment_params(VALID_CONFIG, scoring_model_id="my_model_v2")
    assert ep.scoring_model_id == "my_model_v2"
