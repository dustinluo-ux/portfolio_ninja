from datetime import date
from decimal import Decimal

import pytest

from portfolio_ninja.domain.exceptions import UnknownModelError
from portfolio_ninja.domain.objects import ExperimentParams, MarketState, RunConfig, TickerFeatures
from portfolio_ninja.experiment_engine import create_experiment_params
from portfolio_ninja.scoring_engine import score_tickers

TODAY = date(2026, 1, 15)
VALID_CONFIG = RunConfig(tickers=["AAPL", "MSFT"], run_mode="backtest", window_days=730)


def _make_market_state(tickers=("AAPL", "MSFT")) -> MarketState:
    return MarketState(
        features={
            t: TickerFeatures(
                momentum_20d=Decimal("0.05"),
                volatility_20d=Decimal("0.02"),
                rsi_14=Decimal("55.0"),
                volatility_ewma=Decimal("0.01"),
                scsi=Decimal("0.0"),
            )
            for t in tickers
        },
        as_of_date=TODAY,
        params_hash="d" * 64,
        regime="EXPANSION",
    )


def _make_ep(**kwargs) -> ExperimentParams:
    return create_experiment_params(VALID_CONFIG, **kwargs)


def test_scoring_engine_valid_inputs_returns_complete_score_set():
    ms = _make_market_state()
    ep = _make_ep()
    ss = score_tickers(ms, ep)
    assert ss.validation_status == "valid"
    assert ss.as_of_date == TODAY
    assert len(ss.scores) == 2


def test_scoring_engine_model_id_propagated_from_experiment_params():
    ms = _make_market_state()
    ep = _make_ep()
    ss = score_tickers(ms, ep)
    assert ss.model_id == ep.scoring_model_id


def test_scoring_engine_all_scores_are_decimal_in_zero_to_one_range():
    ms = _make_market_state()
    ep = _make_ep()
    ss = score_tickers(ms, ep)
    for ticker, score in ss.scores.items():
        assert isinstance(score, Decimal)
        assert Decimal("0") <= score <= Decimal("1"), f"{ticker}: {score}"


def test_scoring_engine_unknown_model_id_raises_unknown_model_error():
    ms = _make_market_state()
    ep = ExperimentParams(
        scoring_model_id="nonexistent_model",
        top_n=5,
        rebalance_freq="daily",
        params_hash="e" * 64,
    )
    with pytest.raises(UnknownModelError, match="Unknown model"):
        score_tickers(ms, ep)


def test_scoring_engine_scores_has_entry_for_every_ticker_in_market_state():
    ms = _make_market_state(("AAPL", "MSFT", "GOOG"))
    ep = _make_ep()
    ss = score_tickers(ms, ep)
    assert set(ss.scores.keys()) == {"AAPL", "MSFT", "GOOG"}


def test_scoring_engine_stub_score_is_deterministic_for_same_ticker():
    ms = _make_market_state()
    ep = _make_ep()
    ss1 = score_tickers(ms, ep)
    ss2 = score_tickers(ms, ep)
    assert ss1.scores == ss2.scores


def test_scoring_engine_validation_status_is_valid_on_success():
    ms = _make_market_state()
    ep = _make_ep()
    ss = score_tickers(ms, ep)
    assert ss.validation_status == "valid"


def test_scoring_engine_params_hash_is_deterministic():
    ms = _make_market_state()
    ep = _make_ep()
    ss1 = score_tickers(ms, ep)
    ss2 = score_tickers(ms, ep)
    assert ss1.params_hash == ss2.params_hash
    assert len(ss1.params_hash) == 64


# ── technical_composite_v1 tests ────────────────────────────────────────────


def _make_ep_composite() -> ExperimentParams:
    return create_experiment_params(VALID_CONFIG, scoring_model_id="technical_composite_v1")


def _make_differentiated_market_state() -> MarketState:
    """Three tickers with clearly differentiated factor values for signal testing."""
    return MarketState(
        features={
            "STRONG": TickerFeatures(
                momentum_20d=Decimal("0.15"),   # high momentum
                volatility_20d=Decimal("0.01"),  # low volatility
                rsi_14=Decimal("70.0"),          # high RSI
                volatility_ewma=Decimal("0.01"),
                scsi=Decimal("0.0"),
            ),
            "WEAK": TickerFeatures(
                momentum_20d=Decimal("-0.10"),  # negative momentum
                volatility_20d=Decimal("0.05"),  # high volatility
                rsi_14=Decimal("30.0"),          # low RSI
                volatility_ewma=Decimal("0.01"),
                scsi=Decimal("0.0"),
            ),
            "MID": TickerFeatures(
                momentum_20d=Decimal("0.02"),
                volatility_20d=Decimal("0.03"),
                rsi_14=Decimal("50.0"),
                volatility_ewma=Decimal("0.01"),
                scsi=Decimal("0.0"),
            ),
        },
        as_of_date=TODAY,
        params_hash="f" * 64,
        regime="EXPANSION",
    )


def test_scoring_engine_technical_composite_v1_returns_real_scores():
    ms = _make_differentiated_market_state()
    ep = _make_ep_composite()
    ss = score_tickers(ms, ep)
    assert ss.validation_status == "valid"
    assert ss.model_id == "technical_composite_v1"
    assert set(ss.scores.keys()) == {"STRONG", "WEAK", "MID"}
    for score in ss.scores.values():
        assert isinstance(score, Decimal)
        assert Decimal("0") <= score <= Decimal("1")


def test_scoring_engine_technical_composite_v1_scores_differentiate_tickers():
    ms = _make_differentiated_market_state()
    ep = _make_ep_composite()
    ss = score_tickers(ms, ep)
    scores = ss.scores
    # STRONG should outscore WEAK given high momentum + low vol + high RSI vs opposite
    assert scores["STRONG"] > scores["WEAK"], (
        f"STRONG ({scores['STRONG']}) should > WEAK ({scores['WEAK']})"
    )
    assert scores["STRONG"] > scores["MID"], (
        f"STRONG ({scores['STRONG']}) should > MID ({scores['MID']})"
    )


def test_scoring_engine_technical_composite_v1_high_momentum_scores_higher():
    """Isolate momentum signal: equal vol + RSI, differing only in momentum."""
    ms = MarketState(
        features={
            "HIGH_MOM": TickerFeatures(
                momentum_20d=Decimal("0.20"),
                volatility_20d=Decimal("0.02"),
                rsi_14=Decimal("50.0"),
                volatility_ewma=Decimal("0.01"),
                scsi=Decimal("0.0"),
            ),
            "LOW_MOM": TickerFeatures(
                momentum_20d=Decimal("-0.10"),
                volatility_20d=Decimal("0.02"),
                rsi_14=Decimal("50.0"),
                volatility_ewma=Decimal("0.01"),
                scsi=Decimal("0.0"),
            ),
        },
        as_of_date=TODAY,
        params_hash="a" * 64,
        regime="EXPANSION",
    )
    ep = _make_ep_composite()
    ss = score_tickers(ms, ep)
    assert ss.scores["HIGH_MOM"] > ss.scores["LOW_MOM"]


def test_scoring_engine_technical_composite_v1_all_equal_features_return_half():
    """All tickers with identical features → normalized factors all 0.5 → score = 0.5."""
    ms = _make_market_state(("AAPL", "MSFT", "GOOG"))  # all equal features
    ep = _make_ep_composite()
    ss = score_tickers(ms, ep)
    expected = Decimal("0.4") * Decimal("0.5") + Decimal("0.3") * Decimal("0.5") + Decimal("0.3") * Decimal("0.5")
    for ticker, score in ss.scores.items():
        assert score == expected, f"{ticker}: expected {expected}, got {score}"
