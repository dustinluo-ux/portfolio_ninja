import pytest
from datetime import date
from decimal import Decimal

from portfolio_ninja.domain.objects import TargetPortfolio
from portfolio_ninja.domain.exceptions import WeightSumError
from portfolio_ninja.risk_engine import evaluate_risk

TODAY = date(2026, 1, 15)


def _make_tp(weights: dict[str, str]) -> TargetPortfolio:
    return TargetPortfolio(
        weights={k: Decimal(v) for k, v in weights.items()},
        as_of_date=TODAY,
        params_hash="j" * 64,
    )


def _equal_weights(n: int) -> dict[str, str]:
    w = Decimal("1") / Decimal(str(n))
    residual = Decimal("1.0") - w * n
    tickers = [f"T{i}" for i in range(n)]
    result = {t: str(w) for t in tickers}
    if residual:
        result[tickers[0]] = str(Decimal(result[tickers[0]]) + residual)
    return result


def test_risk_engine_valid_portfolio_returns_approved_risk_decision():
    tp = _make_tp(_equal_weights(5))
    rd = evaluate_risk(tp)
    assert rd.approved is True
    assert rd.validation_status == "valid"


def test_risk_engine_concentration_limit_exceeded_sets_approved_false():
    tp = _make_tp({"AAPL": "0.5", "MSFT": "0.5"})
    rd = evaluate_risk(tp)
    assert rd.approved is False


def test_risk_engine_concentration_limit_exceeded_populates_reason_codes():
    tp = _make_tp({"AAPL": "0.5", "MSFT": "0.5"})
    rd = evaluate_risk(tp)
    assert any("concentration_limit_exceeded" in rc for rc in rd.reason_codes)
    assert any("AAPL" in rc for rc in rd.reason_codes)
    assert any("MSFT" in rc for rc in rd.reason_codes)


def test_risk_engine_weight_sum_not_one_raises_weight_sum_error():
    tp = TargetPortfolio(
        weights={"AAPL": Decimal("0.6"), "MSFT": Decimal("0.6")},
        as_of_date=TODAY,
        params_hash="k" * 64,
    )
    with pytest.raises(WeightSumError):
        evaluate_risk(tp)


def test_risk_engine_empty_weights_raises_value_error():
    tp = TargetPortfolio(
        weights={},
        as_of_date=TODAY,
        params_hash="l" * 64,
    )
    with pytest.raises(ValueError, match="must not be empty"):
        evaluate_risk(tp)


def test_risk_engine_risk_decision_weights_match_target_portfolio_weights():
    tp = _make_tp(_equal_weights(5))
    rd = evaluate_risk(tp)
    assert rd.weights == tp.weights


def test_risk_engine_all_weights_are_decimal():
    tp = _make_tp(_equal_weights(4))
    rd = evaluate_risk(tp)
    for w in rd.weights.values():
        assert isinstance(w, Decimal)


def test_risk_engine_validation_status_is_valid_on_success():
    tp = _make_tp(_equal_weights(5))
    rd = evaluate_risk(tp)
    assert rd.validation_status == "valid"


def test_risk_engine_approved_true_only_when_all_checks_pass():
    # Exactly at the limit (0.25) — should still be approved
    tp = _make_tp({"A": "0.25", "B": "0.25", "C": "0.25", "D": "0.25"})
    rd = evaluate_risk(tp)
    assert rd.approved is True
    # One tick over the limit
    tp2 = TargetPortfolio(
        weights={"A": Decimal("0.2501"), "B": Decimal("0.2499"), "C": Decimal("0.25"), "D": Decimal("0.25")},
        as_of_date=TODAY,
        params_hash="m" * 64,
    )
    rd2 = evaluate_risk(tp2)
    assert rd2.approved is False
