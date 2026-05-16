"""Phase 1 E2E: DataPlane + MarketStateEngine runtime validation with real CSV data.

Tests are skipped if the trading data directory does not exist (CI / machines without local data).
No network calls — RealDataAdapter runs with download_enabled=False.
"""
from datetime import date
from decimal import Decimal

import pytest

from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.data_plane.real_adapter import (
    _DEFAULT_BASE,
    CSV_SUBDIRS,
    RealDataAdapter,
    _find_csv_path,
    _load_csv_bars,
)
from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.market_state_engine import compute_market_state
from portfolio_ninja.universe_gateway import create_universe

_BASE = _DEFAULT_BASE
_WINDOW_DAYS = 120
_MIN_BARS_MARKET_STATE = 21   # MarketStateEngine minimum
_MIN_BARS_ADAPTER = 60        # RealDataAdapter minimum


def _discover_tickers(n: int = 10) -> list[str]:
    tickers: list[str] = []
    for subdir in CSV_SUBDIRS:
        csv_dir = _BASE / subdir
        if not csv_dir.exists():
            continue
        for csv_path in sorted(csv_dir.glob("*.csv")):
            ticker = csv_path.stem.upper()
            if ticker not in tickers:
                tickers.append(ticker)
    return tickers[:n]


def _has_sufficient_bars(ticker: str) -> bool:
    """True iff _load_csv_bars succeeds with the same parameters the pipeline uses."""
    path = _find_csv_path(_BASE, CSV_SUBDIRS, ticker)
    if path is None or not path.exists():
        return False
    try:
        _load_csv_bars(path, ticker, date.today(), _WINDOW_DAYS, min_rows=_MIN_BARS_ADAPTER)
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def real_tickers():
    if not _BASE.exists():
        pytest.skip(f"Trading data directory not found: {_BASE}")
    candidates = _discover_tickers(n=20)
    if not candidates:
        pytest.skip("No CSV files found in trading data directory")
    good = [t for t in candidates if _has_sufficient_bars(t)]
    if not good:
        pytest.skip(f"No tickers with ≥{_MIN_BARS_ADAPTER} in-window bars found among {candidates}")
    return good[:3]


@pytest.fixture(scope="module")
def real_market_dataset(real_tickers):
    config = RunConfig(tickers=real_tickers, run_mode="backtest", window_days=_WINDOW_DAYS)
    universe = create_universe(config)
    adapter = RealDataAdapter(download_enabled=False, base_path=_BASE)
    return fetch_market_data(universe, adapter)


def test_e2e_real_data_market_dataset_returned(real_market_dataset):
    assert real_market_dataset is not None
    assert real_market_dataset.validation_status == "valid"


def test_e2e_real_data_all_tickers_covered(real_market_dataset, real_tickers):
    assert set(real_market_dataset.data.keys()) == set(real_tickers)


def test_e2e_real_data_each_ticker_has_minimum_bars(real_market_dataset):
    for ticker, ticker_data in real_market_dataset.data.items():
        assert len(ticker_data.ohlcv) >= _MIN_BARS_MARKET_STATE, (
            f"{ticker}: only {len(ticker_data.ohlcv)} bars, need ≥{_MIN_BARS_MARKET_STATE}"
        )


def test_e2e_real_data_ohlcv_fields_are_decimal(real_market_dataset):
    for ticker, ticker_data in real_market_dataset.data.items():
        for bar in ticker_data.ohlcv[:5]:  # spot-check first 5 bars
            assert isinstance(bar.open, Decimal), f"{ticker}: open is {type(bar.open)}"
            assert isinstance(bar.high, Decimal), f"{ticker}: high is {type(bar.high)}"
            assert isinstance(bar.low, Decimal), f"{ticker}: low is {type(bar.low)}"
            assert isinstance(bar.close, Decimal), f"{ticker}: close is {type(bar.close)}"
            assert bar.high >= bar.low, f"{ticker}: high < low on {bar.date}"
            assert bar.close > Decimal("0"), f"{ticker}: non-positive close on {bar.date}"


def test_e2e_real_data_params_hash_populated(real_market_dataset):
    assert len(real_market_dataset.params_hash) == 64


def test_e2e_real_data_market_state_computes_from_real_bars(real_market_dataset):
    market_state = compute_market_state(real_market_dataset)
    assert market_state.validation_status == "valid"
    assert set(market_state.features.keys()) == set(real_market_dataset.data.keys())


def test_e2e_real_data_market_state_features_are_decimal(real_market_dataset):
    market_state = compute_market_state(real_market_dataset)
    for ticker, features in market_state.features.items():
        assert isinstance(features.momentum_20d, Decimal), f"{ticker}: momentum not Decimal"
        assert isinstance(features.volatility_20d, Decimal), f"{ticker}: volatility not Decimal"
        assert isinstance(features.rsi_14, Decimal), f"{ticker}: rsi not Decimal"


def test_e2e_real_data_market_state_features_are_nonzero(real_market_dataset):
    market_state = compute_market_state(real_market_dataset)
    for ticker, features in market_state.features.items():
        assert features.volatility_20d > Decimal("0"), f"{ticker}: zero volatility"
        assert Decimal("0") <= features.rsi_14 <= Decimal("100"), f"{ticker}: rsi out of range"


def test_e2e_real_data_sentiment_is_decimal(real_market_dataset):
    for ticker, ticker_data in real_market_dataset.data.items():
        assert isinstance(ticker_data.news_sentiment, Decimal), (
            f"{ticker}: news_sentiment is {type(ticker_data.news_sentiment)}"
        )


def test_e2e_real_data_pe_ratio_is_decimal(real_market_dataset):
    for ticker, ticker_data in real_market_dataset.data.items():
        assert isinstance(ticker_data.pe_ratio, Decimal), (
            f"{ticker}: pe_ratio is {type(ticker_data.pe_ratio)}"
        )
