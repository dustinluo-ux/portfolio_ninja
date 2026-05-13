import pytest
from datetime import date
from decimal import Decimal

from portfolio_ninja.domain.objects import ExecutionIntent, Order
from portfolio_ninja.evaluation_engine import evaluate_cycle

TODAY = date(2026, 1, 15)


def _make_ei(orders=None, params_hash=None) -> ExecutionIntent:
    return ExecutionIntent(
        orders=orders if orders is not None else [
            Order(ticker="AAPL", direction="buy", quantity=Decimal("0.5"), order_type="market"),
        ],
        adapter_id="StubExecutionAdapter",
        run_mode="backtest",
        as_of_date=TODAY,
        params_hash=params_hash if params_hash is not None else "o" * 64,
    )


def test_evaluation_engine_non_empty_orders_returns_evaluation_report():
    ei = _make_ei()
    er = evaluate_cycle(ei)
    assert er.validation_status == "valid"
    assert er.cycle_id != ""


def test_evaluation_engine_empty_orders_returns_zero_metrics_report():
    ei = _make_ei(orders=[])
    er = evaluate_cycle(ei)
    assert er.pnl == Decimal("0")
    assert er.sharpe == Decimal("0")
    assert er.max_drawdown == Decimal("0")
    assert er.validation_status == "valid"


def test_evaluation_engine_empty_orders_populates_reason_codes_no_orders():
    ei = _make_ei(orders=[])
    er = evaluate_cycle(ei)
    assert "no_orders_executed" in er.reason_codes


def test_evaluation_engine_cycle_id_is_non_empty():
    ei = _make_ei()
    er = evaluate_cycle(ei)
    assert len(er.cycle_id) > 0


def test_evaluation_engine_pnl_sharpe_max_drawdown_are_decimal():
    ei = _make_ei()
    er = evaluate_cycle(ei)
    assert isinstance(er.pnl, Decimal)
    assert isinstance(er.sharpe, Decimal)
    assert isinstance(er.max_drawdown, Decimal)


def test_evaluation_engine_stub_metrics_are_zero():
    ei = _make_ei()
    er = evaluate_cycle(ei)
    assert er.pnl == Decimal("0")
    assert er.sharpe == Decimal("0")
    assert er.max_drawdown == Decimal("0")


def test_evaluation_engine_validation_status_is_valid_on_success():
    ei = _make_ei()
    er = evaluate_cycle(ei)
    assert er.validation_status == "valid"


def test_evaluation_engine_as_of_date_propagated_from_execution_intent():
    ei = _make_ei()
    er = evaluate_cycle(ei)
    assert er.as_of_date == TODAY
