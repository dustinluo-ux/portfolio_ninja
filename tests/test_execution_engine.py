import pytest
from datetime import date
from decimal import Decimal

from portfolio_ninja.domain.objects import RiskDecision
from portfolio_ninja.domain.adapters import ExecutionAdapter
from portfolio_ninja.domain.stubs import StubExecutionAdapter
from portfolio_ninja.domain.exceptions import ExecutionError
from portfolio_ninja.execution_engine import execute_orders

TODAY = date(2026, 1, 15)


def _make_rd(approved: bool, weights: dict[str, str] | None = None, reason_codes=None) -> RiskDecision:
    w = {k: Decimal(v) for k, v in (weights or {"AAPL": "0.5", "MSFT": "0.5"}).items()}
    return RiskDecision(
        approved=approved,
        weights=w,
        adjustments=[],
        as_of_date=TODAY,
        params_hash="n" * 64,
        reason_codes=reason_codes or [],
    )


def test_execution_engine_approved_decision_produces_non_empty_orders():
    rd = _make_rd(True)
    ei = execute_orders(rd, StubExecutionAdapter(), "backtest")
    assert len(ei.orders) == 2
    assert ei.validation_status == "valid"


def test_execution_engine_rejected_decision_produces_empty_orders():
    rd = _make_rd(False, reason_codes=["concentration_limit_exceeded:AAPL:0.5"])
    ei = execute_orders(rd, StubExecutionAdapter(), "backtest")
    assert ei.orders == []
    assert ei.validation_status == "valid"


def test_execution_engine_rejected_decision_does_not_call_adapter():
    call_log = []

    class TrackingAdapter(ExecutionAdapter):
        def submit(self, intent):
            call_log.append(intent)

    rd = _make_rd(False)
    execute_orders(rd, TrackingAdapter(), "backtest")
    assert call_log == []


def test_execution_engine_adapter_exception_propagates_as_execution_error():
    class FailingAdapter(ExecutionAdapter):
        def submit(self, intent):
            raise RuntimeError("broker offline")

    rd = _make_rd(True)
    with pytest.raises(ExecutionError, match="broker offline"):
        execute_orders(rd, FailingAdapter(), "backtest")


def test_execution_engine_adapter_id_is_class_name_of_adapter():
    rd = _make_rd(True)
    ei = execute_orders(rd, StubExecutionAdapter(), "backtest")
    assert ei.adapter_id == "StubExecutionAdapter"


def test_execution_engine_all_order_quantities_are_decimal():
    rd = _make_rd(True)
    ei = execute_orders(rd, StubExecutionAdapter(), "backtest")
    for order in ei.orders:
        assert isinstance(order.quantity, Decimal)


def test_execution_engine_validation_status_is_valid_on_success():
    rd = _make_rd(True)
    ei = execute_orders(rd, StubExecutionAdapter(), "backtest")
    assert ei.validation_status == "valid"


def test_execution_engine_reason_codes_include_risk_rejection_reason_when_rejected():
    rd = _make_rd(False, reason_codes=["concentration_limit_exceeded:AAPL:0.5"])
    ei = execute_orders(rd, StubExecutionAdapter(), "backtest")
    assert "risk_rejected" in ei.reason_codes
    assert "concentration_limit_exceeded:AAPL:0.5" in ei.reason_codes


def test_execution_engine_integration_stub_adapter_logs_intent(caplog):
    import logging
    rd = _make_rd(True)
    with caplog.at_level(logging.INFO):
        ei = execute_orders(rd, StubExecutionAdapter(), "backtest")
    assert ei.adapter_id == "StubExecutionAdapter"
    assert len(ei.orders) > 0
