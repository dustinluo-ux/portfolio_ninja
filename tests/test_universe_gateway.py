from datetime import date

import pytest

from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.universe_gateway import create_universe

TODAY = date(2026, 1, 15)
VALID_CONFIG = RunConfig(tickers=["AAPL", "MSFT", "GOOG"], run_mode="backtest", window_days=730)


def test_universe_gateway_valid_config_returns_valid_universe():
    u = create_universe(VALID_CONFIG, as_of_date=TODAY)
    assert u.validation_status == "valid"
    assert u.tickers == ["AAPL", "GOOG", "MSFT"]
    assert u.run_mode == "backtest"
    assert u.window_days == 730
    assert u.as_of_date == TODAY
    assert u.params_hash != ""
    assert u.reason_codes == []


def test_universe_gateway_empty_tickers_raises_value_error():
    config = RunConfig(tickers=[], run_mode="backtest", window_days=730)
    with pytest.raises(ValueError, match="tickers must not be empty"):
        create_universe(config, as_of_date=TODAY)


def test_universe_gateway_invalid_run_mode_raises_value_error():
    config = RunConfig(tickers=["AAPL"], run_mode="invalid", window_days=730)
    with pytest.raises(ValueError, match="run_mode"):
        create_universe(config, as_of_date=TODAY)


def test_universe_gateway_window_days_zero_raises_value_error():
    config = RunConfig(tickers=["AAPL"], run_mode="backtest", window_days=0)
    with pytest.raises(ValueError, match="window_days must be > 0"):
        create_universe(config, as_of_date=TODAY)


def test_universe_gateway_window_days_negative_raises_value_error():
    config = RunConfig(tickers=["AAPL"], run_mode="backtest", window_days=-10)
    with pytest.raises(ValueError, match="window_days must be > 0"):
        create_universe(config, as_of_date=TODAY)


def test_universe_gateway_duplicate_tickers_are_deduplicated_and_reason_code_set():
    config = RunConfig(tickers=["AAPL", "MSFT", "AAPL"], run_mode="backtest", window_days=730)
    u = create_universe(config, as_of_date=TODAY)
    assert u.tickers == ["AAPL", "MSFT"]
    assert "tickers_deduplicated" in u.reason_codes
    assert u.validation_status == "valid"


def test_universe_gateway_params_hash_is_deterministic_for_same_inputs():
    u1 = create_universe(VALID_CONFIG, as_of_date=TODAY)
    u2 = create_universe(VALID_CONFIG, as_of_date=TODAY)
    assert u1.params_hash == u2.params_hash
    assert len(u1.params_hash) == 64


def test_universe_gateway_validation_status_is_valid_on_success():
    u = create_universe(VALID_CONFIG, as_of_date=TODAY)
    assert u.validation_status == "valid"


def test_universe_gateway_spy_injected_into_regime_tickers():
    u = create_universe(VALID_CONFIG, as_of_date=TODAY)
    assert "SPY" in u.regime_tickers
    assert "SPY" not in u.tickers


def test_universe_gateway_spy_already_in_tickers_still_in_regime_tickers():
    config = RunConfig(tickers=["SPY", "AAPL"], run_mode="backtest", window_days=730)
    u = create_universe(config, as_of_date=TODAY)
    assert "SPY" in u.regime_tickers
    assert "SPY" in u.tickers
