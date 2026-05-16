from datetime import date
from decimal import Decimal

import pytest

from portfolio_ninja.domain.objects import ExperimentParams, RankedUniverse
from portfolio_ninja.portfolio_construction_engine import construct_portfolio

TODAY = date(2026, 1, 15)


def _make_ranked(tickers_scores: list[tuple[str, str]]) -> RankedUniverse:
    return RankedUniverse(
        ranked=[(t, Decimal(s)) for t, s in tickers_scores],
        as_of_date=TODAY,
        params_hash="g" * 64,
    )


def _make_ep(top_n: int = 3) -> ExperimentParams:
    return ExperimentParams(
        scoring_model_id="stub_v1",
        top_n=top_n,
        rebalance_freq="daily",
        params_hash="h" * 64,
    )


def test_portfolio_construction_engine_valid_inputs_returns_target_portfolio():
    ru = _make_ranked([("AAPL", "0.8"), ("MSFT", "0.7"), ("GOOG", "0.6")])
    ep = _make_ep(top_n=3)
    tp = construct_portfolio(ru, ep)
    assert tp.validation_status == "valid"
    assert tp.as_of_date == TODAY
    assert len(tp.weights) == 3


def test_portfolio_construction_engine_weights_are_equal_for_all_selected_tickers():
    ru = _make_ranked([("AAPL", "0.8"), ("MSFT", "0.7"), ("GOOG", "0.6")])
    ep = _make_ep(top_n=3)
    tp = construct_portfolio(ru, ep)
    values = list(tp.weights.values())
    # All weights should be very close (within Decimal residual adjustment)
    assert max(values) - min(values) < Decimal("0.000000001")


def test_portfolio_construction_engine_weights_sum_exactly_to_one():
    ru = _make_ranked([("AAPL", "0.8"), ("MSFT", "0.7"), ("GOOG", "0.6")])
    ep = _make_ep(top_n=3)
    tp = construct_portfolio(ru, ep)
    assert sum(tp.weights.values()) == Decimal("1.0")


def test_portfolio_construction_engine_top_n_greater_than_available_selects_all():
    ru = _make_ranked([("AAPL", "0.8"), ("MSFT", "0.7")])
    ep = _make_ep(top_n=5)
    tp = construct_portfolio(ru, ep)
    assert len(tp.weights) == 2
    assert sum(tp.weights.values()) == Decimal("1.0")


def test_portfolio_construction_engine_empty_ranked_universe_raises_value_error():
    ru = _make_ranked([])
    ep = _make_ep(top_n=3)
    with pytest.raises(ValueError, match="RankedUniverse must not be empty"):
        construct_portfolio(ru, ep)


def test_portfolio_construction_engine_top_n_zero_raises_value_error():
    ru = _make_ranked([("AAPL", "0.8")])
    ep = ExperimentParams(
        scoring_model_id="stub_v1",
        top_n=0,
        rebalance_freq="daily",
        params_hash="i" * 64,
    )
    with pytest.raises(ValueError, match="top_n must be >= 1"):
        construct_portfolio(ru, ep)


def test_portfolio_construction_engine_all_weights_are_decimal():
    ru = _make_ranked([("AAPL", "0.8"), ("MSFT", "0.7")])
    ep = _make_ep(top_n=2)
    tp = construct_portfolio(ru, ep)
    for w in tp.weights.values():
        assert isinstance(w, Decimal)


def test_portfolio_construction_engine_validation_status_is_valid_on_success():
    ru = _make_ranked([("AAPL", "0.8")])
    ep = _make_ep(top_n=1)
    tp = construct_portfolio(ru, ep)
    assert tp.validation_status == "valid"


def test_portfolio_construction_engine_top_n_capped_populates_reason_codes():
    ru = _make_ranked([("AAPL", "0.8"), ("MSFT", "0.7")])
    ep = _make_ep(top_n=5)
    tp = construct_portfolio(ru, ep)
    assert any("top_n_capped" in rc for rc in tp.reason_codes)


def test_portfolio_construction_engine_contraction_caps_at_3():
    tickers = [(f"T{i}", str(1.0 - i * 0.05)) for i in range(6)]
    ru = _make_ranked(tickers)
    ep = _make_ep(top_n=6)
    tp = construct_portfolio(ru, ep, regime="CONTRACTION")
    assert len(tp.weights) == 3


def test_portfolio_construction_engine_expansion_caps_at_5():
    tickers = [(f"T{i}", str(1.0 - i * 0.05)) for i in range(7)]
    ru = _make_ranked(tickers)
    ep = _make_ep(top_n=7)
    tp = construct_portfolio(ru, ep, regime="EXPANSION")
    assert len(tp.weights) == 5
