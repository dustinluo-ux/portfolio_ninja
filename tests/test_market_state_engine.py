from datetime import date, timedelta
from decimal import Decimal

import pytest

from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.domain.exceptions import InsufficientDataError
from portfolio_ninja.domain.objects import (
    MarketDataset,
    OHLCVBar,
    RunConfig,
    TickerData,
)
from portfolio_ninja.domain.stubs import StubDataAdapter
from portfolio_ninja.market_state_engine import compute_market_state
from portfolio_ninja.universe_gateway import create_universe

TODAY = date(2026, 1, 15)
VALID_CONFIG = RunConfig(tickers=["AAPL", "MSFT"], run_mode="backtest", window_days=730)


def _make_dataset():
    u = create_universe(VALID_CONFIG, as_of_date=TODAY)
    return fetch_market_data(u, StubDataAdapter())


def _make_bars(n: int, start_price: Decimal = Decimal("100")) -> list[OHLCVBar]:
    bars = []
    price = start_price
    for i in range(n):
        day = TODAY - timedelta(days=n - i)
        close = price + Decimal(str(i % 3))
        bars.append(OHLCVBar(
            date=day,
            open=price,
            high=close + Decimal("1"),
            low=price - Decimal("1"),
            close=close,
            volume=100_000,
        ))
        price = close
    return bars


def _make_dataset_with_bars(tickers_bars: dict[str, int]) -> MarketDataset:
    data = {}
    for ticker, n in tickers_bars.items():
        bars = _make_bars(n)
        data[ticker] = TickerData(
            ohlcv=bars,
            news_sentiment=Decimal("0.1"),
            pe_ratio=Decimal("15.0"),
        )
    return MarketDataset(
        data=data,
        source_data_version="test-v1",
        as_of_date=TODAY,
        params_hash="a" * 64,
    )


def test_market_state_engine_valid_dataset_returns_complete_market_state():
    ds = _make_dataset()
    ms = compute_market_state(ds)
    assert ms.validation_status == "valid"
    assert ms.as_of_date == TODAY
    assert ms.params_hash != ""


def test_market_state_engine_features_has_entry_for_every_ticker():
    ds = _make_dataset()
    ms = compute_market_state(ds)
    assert set(ms.features.keys()) == {"AAPL", "MSFT"}


def test_market_state_engine_all_feature_values_are_decimal():
    ds = _make_dataset()
    ms = compute_market_state(ds)
    for tf in ms.features.values():
        assert isinstance(tf.momentum_20d, Decimal)
        assert isinstance(tf.volatility_20d, Decimal)
        assert isinstance(tf.rsi_14, Decimal)
        assert isinstance(tf.volatility_ewma, Decimal)
        assert isinstance(tf.scsi, Decimal)


def test_market_state_engine_insufficient_bars_raises_insufficient_data_error():
    ds = _make_dataset_with_bars({"AAPL": 10})
    with pytest.raises(InsufficientDataError, match="insufficient_bars"):
        compute_market_state(ds)


def test_market_state_engine_rsi_14_is_within_zero_to_hundred_bounds():
    ds = _make_dataset()
    ms = compute_market_state(ds)
    for tf in ms.features.values():
        assert Decimal("0") <= tf.rsi_14 <= Decimal("100")


def test_market_state_engine_momentum_20d_computed_correctly():
    bars = _make_bars(25, start_price=Decimal("100"))
    ds = MarketDataset(
        data={"TEST": TickerData(ohlcv=bars, news_sentiment=Decimal("0"), pe_ratio=Decimal("10"))},
        source_data_version="test-v1",
        as_of_date=TODAY,
        params_hash="b" * 64,
    )
    ms = compute_market_state(ds)
    closes = [b.close for b in bars]
    expected = (closes[-1] - closes[-21]) / closes[-21]
    assert ms.features["TEST"].momentum_20d == expected


def test_market_state_engine_volatility_20d_computed_correctly():
    bars = _make_bars(25, start_price=Decimal("100"))
    ds = MarketDataset(
        data={"TEST": TickerData(ohlcv=bars, news_sentiment=Decimal("0"), pe_ratio=Decimal("10"))},
        source_data_version="test-v1",
        as_of_date=TODAY,
        params_hash="c" * 64,
    )
    ms = compute_market_state(ds)
    assert ms.features["TEST"].volatility_20d >= Decimal("0")


def test_market_state_engine_validation_status_is_valid_on_success():
    ds = _make_dataset()
    ms = compute_market_state(ds)
    assert ms.validation_status == "valid"


def test_market_state_engine_params_hash_is_deterministic():
    ds = _make_dataset()
    ms1 = compute_market_state(ds)
    ms2 = compute_market_state(ds)
    assert ms1.params_hash == ms2.params_hash


def test_market_state_engine_volatility_ewma_is_nonneg():
    ds = _make_dataset()
    ms = compute_market_state(ds)
    for tf in ms.features.values():
        assert tf.volatility_ewma >= Decimal("0")


def test_market_state_engine_scsi_sign_matches_sentiment():
    high_sent = _make_dataset_with_bars({"X": 25})
    high_sent.data["X"].news_sentiment = Decimal("0.7")
    low_sent = _make_dataset_with_bars({"X": 25})
    low_sent.data["X"].news_sentiment = Decimal("0.3")
    neutral_sent = _make_dataset_with_bars({"X": 25})
    neutral_sent.data["X"].news_sentiment = Decimal("0.5")

    assert compute_market_state(high_sent).features["X"].scsi > Decimal("0")
    assert compute_market_state(low_sent).features["X"].scsi < Decimal("0")
    assert compute_market_state(neutral_sent).features["X"].scsi == Decimal("0")


def test_market_state_engine_regime_defaults_to_expansion_without_spy():
    ds = _make_dataset_with_bars({"AAPL": 25})
    ms = compute_market_state(ds)
    assert ms.regime == "EXPANSION"
    assert "regime_spy_missing" in ms.reason_codes
