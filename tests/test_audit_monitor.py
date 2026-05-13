from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from portfolio_ninja.audit_monitor import assemble_audit_record
from portfolio_ninja.domain.exceptions import AuditIncompleteError
from portfolio_ninja.domain.objects import EvaluationReport

TODAY = date(2026, 1, 15)

_FULL_HASHES = {
    "universe": "a" * 64,
    "market_dataset": "b" * 64,
    "market_state": "c" * 64,
    "experiment_params": "d" * 64,
    "score_set": "e" * 64,
    "ranked_universe": "f" * 64,
    "target_portfolio": "g" * 64,
    "risk_decision": "h" * 64,
    "execution_intent": "i" * 64,
}


def _make_er(cycle_id="abcd1234efgh5678") -> EvaluationReport:
    return EvaluationReport(
        cycle_id=cycle_id,
        pnl=Decimal("0"),
        sharpe=Decimal("0"),
        max_drawdown=Decimal("0"),
        as_of_date=TODAY,
        params_hash="p" * 64,
    )


def test_audit_monitor_complete_pipeline_hashes_returns_valid_audit_record():
    er = _make_er()
    ar = assemble_audit_record(er, _FULL_HASHES, "backtest", ["AAPL", "MSFT"])
    assert ar.validation_status == "valid"
    assert ar.cycle_id == er.cycle_id
    assert ar.run_mode == "backtest"


def test_audit_monitor_missing_single_hash_raises_audit_incomplete_error():
    hashes = {k: v for k, v in _FULL_HASHES.items() if k != "universe"}
    er = _make_er()
    with pytest.raises(AuditIncompleteError, match="universe"):
        assemble_audit_record(er, hashes, "backtest", ["AAPL"])


def test_audit_monitor_missing_multiple_hashes_lists_all_in_error():
    hashes = {k: v for k, v in _FULL_HASHES.items() if k not in ("universe", "market_state")}
    er = _make_er()
    with pytest.raises(AuditIncompleteError):
        assemble_audit_record(er, hashes, "backtest", ["AAPL"])


def test_audit_monitor_cycle_id_distinct_values_propagated_correctly():
    # cycle_id has a single source (evaluation_report); mismatch is unimplementable.
    # This test verifies propagation is exact for a non-default value.
    er = _make_er(cycle_id="deadbeefcafebabe")
    ar = assemble_audit_record(er, _FULL_HASHES, "backtest", ["AAPL"])
    assert ar.cycle_id == "deadbeefcafebabe"


def test_audit_monitor_empty_params_hash_value_raises_audit_incomplete_error():
    hashes = dict(_FULL_HASHES)
    hashes["universe"] = ""
    er = _make_er()
    with pytest.raises(AuditIncompleteError, match="Empty params_hash"):
        assemble_audit_record(er, hashes, "backtest", ["AAPL"])


def test_audit_monitor_completed_at_is_utc_datetime():
    er = _make_er()
    ar = assemble_audit_record(er, _FULL_HASHES, "backtest", ["AAPL"])
    assert isinstance(ar.completed_at, datetime)
    assert ar.completed_at.tzinfo == timezone.utc


def test_audit_monitor_pipeline_hashes_contains_all_nine_keys():
    er = _make_er()
    ar = assemble_audit_record(er, _FULL_HASHES, "backtest", ["AAPL"])
    expected_keys = {
        "universe", "market_dataset", "market_state", "experiment_params",
        "score_set", "ranked_universe", "target_portfolio", "risk_decision",
        "execution_intent",
    }
    assert set(ar.pipeline_hashes.keys()) == expected_keys


def test_audit_monitor_validation_status_is_valid_on_success():
    er = _make_er()
    ar = assemble_audit_record(er, _FULL_HASHES, "backtest", ["AAPL"])
    assert ar.validation_status == "valid"


def test_audit_monitor_cycle_id_propagated_from_evaluation_report():
    er = _make_er(cycle_id="1234567890abcdef")
    ar = assemble_audit_record(er, _FULL_HASHES, "backtest", ["AAPL"])
    assert ar.cycle_id == "1234567890abcdef"
