"""RealDataAdapter tests.

Tests the CSV-based RealDataAdapter against pre-downloaded data at C:\\portfolio_ninja\trading_data\\.
"""

import hashlib
import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from portfolio_ninja.data_plane.real_adapter import CSV_SUBDIRS, RealDataAdapter, _find_csv_path
from portfolio_ninja.domain.exceptions import (
    IncompleteDataError,
)
from portfolio_ninja.domain.objects import Universe

TRADING_DATA = Path("C:/portfolio_ninja/trading_data/stock_market_data")
TODAY = date(2026, 5, 14)


def _make_universe(tickers: list[str], window_days: int = 200, as_of: date = TODAY) -> Universe:
    return Universe(
        tickers=tickers,
        run_mode="backtest",
        window_days=window_days,
        as_of_date=as_of,
        params_hash=hashlib.sha256(json.dumps({"tickers": tickers}).encode()).hexdigest(),
    )


# ── Real data tests ─────────────────────────────────────────────────────────


def test_real_adapter_fetches_nvda_and_msft():
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u = _make_universe(["NVDA", "MSFT"])
    ds = adapter.fetch(u, u.window_days)

    assert "NVDA" in ds.data
    assert "MSFT" in ds.data
    assert ds.validation_status == "valid"
    assert ds.source_data_version == "csv-real"
    assert len(ds.data["NVDA"].ohlcv) > 0
    assert len(ds.data["MSFT"].ohlcv) > 0


def test_real_adapter_all_prices_decimal():
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u = _make_universe(["NVDA", "MSFT"])
    ds = adapter.fetch(u, u.window_days)

    for ticker, td in ds.data.items():
        for bar in td.ohlcv:
            assert isinstance(bar.open, Decimal), f"{ticker}.open not Decimal"
            assert isinstance(bar.high, Decimal), f"{ticker}.high not Decimal"
            assert isinstance(bar.low, Decimal), f"{ticker}.low not Decimal"
            assert isinstance(bar.close, Decimal), f"{ticker}.close not Decimal"
        assert isinstance(td.news_sentiment, Decimal)
        assert isinstance(td.pe_ratio, Decimal)


def test_real_adapter_ohlcv_integrity():
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u = _make_universe(["MSFT"])
    ds = adapter.fetch(u, u.window_days)

    for ticker, td in ds.data.items():
        for bar in td.ohlcv:
            assert bar.high >= bar.low, f"{ticker} on {bar.date}: high={bar.high} < low={bar.low}"
            assert bar.volume >= 0, f"{ticker} on {bar.date}: negative volume"


def test_real_adapter_deterministic_hashes():
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u = _make_universe(["NVDA", "MSFT"])

    ds1 = adapter.fetch(u, u.window_days)
    ds2 = adapter.fetch(u, u.window_days)

    assert ds1.params_hash == ds2.params_hash
    assert ds1.source_data_version == ds2.source_data_version
    assert ds1.data["NVDA"].ohlcv[0].close == ds2.data["NVDA"].ohlcv[0].close


def test_real_adapter_different_tickers_produce_different_data():
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u_nvda = _make_universe(["NVDA"])
    u_aapl = _make_universe(["AAPL"])

    ds_nvda = adapter.fetch(u_nvda, u_nvda.window_days)
    ds_aapl = adapter.fetch(u_aapl, u_aapl.window_days)

    assert ds_nvda.params_hash != ds_aapl.params_hash
    assert set(ds_nvda.data.keys()) == {"NVDA"}
    assert set(ds_aapl.data.keys()) == {"AAPL"}
    assert ds_nvda.data["NVDA"].ohlcv[0].close != ds_aapl.data["AAPL"].ohlcv[0].close


# ── Fail-loud behavior ──────────────────────────────────────────────────────


def test_real_adapter_missing_ticker_fails_loud():
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u = _make_universe(["NONEXISTENT_TICKER_999"])

    with pytest.raises(IncompleteDataError, match="NONEXISTENT_TICKER_999"):
        adapter.fetch(u, 30)


def test_real_adapter_minimum_rows_enforced():
    """A tiny CSV (<60 rows) should be found but fail with InsufficientDataError."""
    with tempfile.TemporaryDirectory() as tmp:
        csv_dir = Path(tmp) / "nasdaq/csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        csv_path = csv_dir / "BADTICKER.csv"

        with open(csv_path, "w") as f:
            f.write("Date,Open,High,Low,Close,Volume,Adjusted Close\n")
            f.write("2026-01-01,100,101,99,100.5,1000000,100.5\n")
            f.write("2026-01-02,101,102,100,101.5,1000000,101.5\n")
            f.write("2026-01-03,102,103,101,102.5,1000000,102.5\n")
            f.write("2026-01-04,103,104,102,103.5,1000000,103.5\n")
            f.write("2026-01-05,104,105,103,104.5,1000000,104.5\n")

        adapter = RealDataAdapter(base_path=Path(tmp), subdirs=CSV_SUBDIRS)
        u = _make_universe(["BADTICKER"], window_days=30)

        # Exception bubbles up to outer handler which catches Exception and logs
        # then adds to missing → IncompleteDataError
        with pytest.raises(IncompleteDataError, match="BADTICKER"):
            adapter.fetch(u, 30)

# ── Utility tests ───────────────────────────────────────────────────────────


def test_find_csv_path_locates_ticker():
    path = _find_csv_path(TRADING_DATA, CSV_SUBDIRS, "NVDA")
    assert path is not None
    assert path.stem.upper() == "NVDA"


def test_find_csv_path_returns_none_for_missing():
    path = _find_csv_path(TRADING_DATA, CSV_SUBDIRS, "NONEXISTENT_999")
    assert path is None
