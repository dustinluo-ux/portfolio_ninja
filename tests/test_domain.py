"""Tests for the domain layer — all 22 required tests from the domain_objects contract."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.portfolio_ninja.domain import (
    AuditRecord,
    EvaluationReport,
    ExecutionIntent,
    ExperimentParams,
    MarketDataset,
    MarketState,
    OHLCVBar,
    Order,
    RankedUniverse,
    RiskDecision,
    ScoreSet,
    StubDataAdapter,
    TargetPortfolio,
    TickerData,
    TickerFeatures,
    Universe,
)
from src.portfolio_ninja.domain.exceptions import AuditIncompleteError

TODAY = date(2026, 1, 15)
TEST_HASH = hashlib.sha256(b"test").hexdigest()

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _valid_universe() -> Universe:
    return Universe(
        tickers=["AAPL", "MSFT"],
        run_mode="backtest",
        window_days=730,
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )


def _valid_ticker_data() -> TickerData:
    bar = OHLCVBar(
        date=TODAY,
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("99.00"),
        close=Decimal("103.00"),
        volume=500_000,
    )
    return TickerData(ohlcv=[bar], news_sentiment=Decimal("0.5"), pe_ratio=Decimal("20.00"))


def _valid_ticker_features(rsi: Decimal = Decimal("55.0")) -> TickerFeatures:
    return TickerFeatures(
        momentum_20d=Decimal("0.03"),
        volatility_20d=Decimal("0.02"),
        rsi_14=rsi,
    )


def _all_pipeline_hashes() -> dict[str, str]:
    return {
        "universe": TEST_HASH,
        "market_dataset": TEST_HASH,
        "market_state": TEST_HASH,
        "experiment_params": TEST_HASH,
        "score_set": TEST_HASH,
        "ranked_universe": TEST_HASH,
        "target_portfolio": TEST_HASH,
        "risk_decision": TEST_HASH,
        "execution_intent": TEST_HASH,
    }


# ---------------------------------------------------------------------------
# Universe tests
# ---------------------------------------------------------------------------

def test_domain_universe_validate_valid_state_passes() -> None:
    u = _valid_universe()
    u.validate()  # must not raise


def test_domain_universe_validate_empty_tickers_raises_value_error() -> None:
    u = Universe(
        tickers=[],
        run_mode="backtest",
        window_days=730,
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    with pytest.raises(ValueError, match="tickers"):
        u.validate()


def test_domain_universe_validate_invalid_run_mode_raises_value_error() -> None:
    u = Universe(
        tickers=["AAPL"],
        run_mode="invalid",
        window_days=730,
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    with pytest.raises(ValueError, match="run_mode"):
        u.validate()


# ---------------------------------------------------------------------------
# MarketDataset tests
# ---------------------------------------------------------------------------

def test_domain_market_dataset_validate_valid_state_passes() -> None:
    ds = MarketDataset(
        data={"AAPL": _valid_ticker_data()},
        source_data_version="stub-v1",
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    ds.validate()  # must not raise


def test_domain_market_dataset_validate_empty_source_data_version_raises_value_error() -> None:
    ds = MarketDataset(
        data={"AAPL": _valid_ticker_data()},
        source_data_version="",
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    with pytest.raises(ValueError, match="source_data_version"):
        ds.validate()


# ---------------------------------------------------------------------------
# MarketState tests
# ---------------------------------------------------------------------------

def test_domain_market_state_validate_valid_state_passes() -> None:
    ms = MarketState(
        features={"AAPL": _valid_ticker_features()},
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    ms.validate()  # must not raise


def test_domain_market_state_validate_rsi_out_of_range_raises_value_error() -> None:
    ms = MarketState(
        features={"AAPL": _valid_ticker_features(rsi=Decimal("101"))},
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    with pytest.raises(ValueError, match="rsi_14"):
        ms.validate()


# ---------------------------------------------------------------------------
# ExperimentParams tests
# ---------------------------------------------------------------------------

def test_domain_experiment_params_validate_valid_state_passes() -> None:
    ep = ExperimentParams(
        scoring_model_id="model-v1",
        top_n=5,
        rebalance_freq="weekly",
        params_hash=TEST_HASH,
    )
    ep.validate()  # must not raise


def test_domain_experiment_params_validate_top_n_zero_raises_value_error() -> None:
    ep = ExperimentParams(
        scoring_model_id="model-v1",
        top_n=0,
        rebalance_freq="weekly",
        params_hash=TEST_HASH,
    )
    with pytest.raises(ValueError, match="top_n"):
        ep.validate()


# ---------------------------------------------------------------------------
# ScoreSet tests
# ---------------------------------------------------------------------------

def test_domain_score_set_validate_valid_state_passes() -> None:
    ss = ScoreSet(
        scores={"AAPL": Decimal("0.8"), "MSFT": Decimal("0.6")},
        model_id="model-v1",
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    ss.validate()  # must not raise


def test_domain_score_set_validate_score_out_of_range_raises_value_error() -> None:
    ss = ScoreSet(
        scores={"AAPL": Decimal("1.5")},
        model_id="model-v1",
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    with pytest.raises(ValueError, match="AAPL"):
        ss.validate()


# ---------------------------------------------------------------------------
# RankedUniverse tests
# ---------------------------------------------------------------------------

def test_domain_ranked_universe_validate_valid_state_passes() -> None:
    ru = RankedUniverse(
        ranked=[("AAPL", Decimal("0.9")), ("MSFT", Decimal("0.7"))],
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    ru.validate()  # must not raise


# ---------------------------------------------------------------------------
# TargetPortfolio tests
# ---------------------------------------------------------------------------

def test_domain_target_portfolio_validate_weights_sum_to_one_passes() -> None:
    tp = TargetPortfolio(
        weights={"AAPL": Decimal("0.6"), "MSFT": Decimal("0.4")},
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    tp.validate()  # must not raise


def test_domain_target_portfolio_validate_weights_not_sum_to_one_raises_value_error() -> None:
    tp = TargetPortfolio(
        weights={"AAPL": Decimal("0.3"), "MSFT": Decimal("0.2")},
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    with pytest.raises(ValueError, match="sum"):
        tp.validate()


# ---------------------------------------------------------------------------
# RiskDecision tests
# ---------------------------------------------------------------------------

def test_domain_risk_decision_validate_valid_state_passes() -> None:
    rd = RiskDecision(
        approved=True,
        weights={"AAPL": Decimal("0.6"), "MSFT": Decimal("0.4")},
        adjustments=[],
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    rd.validate()  # must not raise


# ---------------------------------------------------------------------------
# ExecutionIntent tests
# ---------------------------------------------------------------------------

def test_domain_execution_intent_validate_valid_state_passes() -> None:
    order = Order(ticker="AAPL", direction="buy", quantity=Decimal("10"))
    ei = ExecutionIntent(
        orders=[order],
        adapter_id="stub",
        run_mode="backtest",
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    ei.validate()  # must not raise


# ---------------------------------------------------------------------------
# EvaluationReport tests
# ---------------------------------------------------------------------------

def test_domain_evaluation_report_validate_valid_state_passes() -> None:
    er = EvaluationReport(
        cycle_id="cycle-001",
        pnl=Decimal("1500.00"),
        sharpe=Decimal("1.25"),
        max_drawdown=Decimal("-0.08"),
        as_of_date=TODAY,
        params_hash=TEST_HASH,
    )
    er.validate()  # must not raise


# ---------------------------------------------------------------------------
# AuditRecord tests
# ---------------------------------------------------------------------------

def test_domain_audit_record_validate_valid_state_passes() -> None:
    ar = AuditRecord(
        cycle_id="cycle-001",
        run_mode="backtest",
        tickers=["AAPL", "MSFT"],
        pipeline_hashes=_all_pipeline_hashes(),
        completed_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    ar.validate()  # must not raise


def test_domain_audit_record_validate_missing_pipeline_hash_raises_value_error() -> None:
    hashes = _all_pipeline_hashes()
    del hashes["universe"]
    ar = AuditRecord(
        cycle_id="cycle-001",
        run_mode="backtest",
        tickers=["AAPL"],
        pipeline_hashes=hashes,
        completed_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    with pytest.raises(AuditIncompleteError, match="universe"):
        ar.validate()


# ---------------------------------------------------------------------------
# StubDataAdapter determinism test
# ---------------------------------------------------------------------------

def test_domain_stub_data_adapter_is_deterministic_for_same_inputs() -> None:
    universe = _valid_universe()
    adapter = StubDataAdapter(seed=42)

    result1 = adapter.fetch(universe, window_days=20)
    result2 = adapter.fetch(universe, window_days=20)

    assert result1.params_hash == result2.params_hash
    assert set(result1.data.keys()) == set(result2.data.keys())
    for ticker in result1.data:
        bars1 = result1.data[ticker].ohlcv
        bars2 = result2.data[ticker].ohlcv
        assert len(bars1) == len(bars2)
        for b1, b2 in zip(bars1, bars2):
            assert b1.date == b2.date
            assert b1.open == b2.open
            assert b1.high == b2.high
            assert b1.low == b2.low
            assert b1.close == b2.close
            assert b1.volume == b2.volume
        assert result1.data[ticker].news_sentiment == result2.data[ticker].news_sentiment
        assert result1.data[ticker].pe_ratio == result2.data[ticker].pe_ratio


# ---------------------------------------------------------------------------
# OHLCVBar invariant test
# ---------------------------------------------------------------------------

def test_domain_ohlcv_bar_high_gte_low_invariant() -> None:
    bar = OHLCVBar(
        date=TODAY,
        open=Decimal("100.00"),
        high=Decimal("98.00"),   # high < low — invalid
        low=Decimal("99.00"),
        close=Decimal("100.00"),
        volume=100_000,
    )
    with pytest.raises(ValueError, match="high"):
        bar.validate()


# ---------------------------------------------------------------------------
# Order direction test
# ---------------------------------------------------------------------------

def test_domain_order_direction_must_be_buy_or_sell() -> None:
    order = Order(ticker="AAPL", direction="hold", quantity=Decimal("10"))
    with pytest.raises(ValueError, match="direction"):
        order.validate()
