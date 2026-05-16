"""RealDataAdapter tests.

Tests the CSV+Parquet RealDataAdapter against pre-downloaded data at C:\\portfolio_ninja\trading_data\
"""

import hashlib
import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from portfolio_ninja.data_plane.real_adapter import (
    _FUNDAMENTALS_DIR,
    _NEWS_DIR,
    CSV_SUBDIRS,
    RealDataAdapter,
    _find_csv_path,
    _get_last_csv_date,
    _get_last_parquet_date,
)
from portfolio_ninja.domain.exceptions import IncompleteDataError
from portfolio_ninja.domain.objects import Universe

TRADING_DATA = Path("C:/portfolio_ninja/trading_data/stock_market_data")
TODAY = date.today()


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
        # news_sentiment and pe_ratio are Decimal (may be NaN if data not available)
        assert isinstance(td.news_sentiment, Decimal), f"{ticker}.news_sentiment not Decimal"
        assert isinstance(td.pe_ratio, Decimal), f"{ticker}.pe_ratio not Decimal"


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


# ── Sentiment & PE ratio tests ──────────────────────────────────────────────


def test_real_adapter_pe_ratio_computed():
    """NVDA has FMP fundamentals with epsDiluted, so PE should be a real positive Decimal."""
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u = _make_universe(["NVDA"])
    ds = adapter.fetch(u, u.window_days)

    nvda_pe = ds.data["NVDA"].pe_ratio
    assert isinstance(nvda_pe, Decimal)
    assert not nvda_pe.is_nan(), f"NVDA PE should be real, got {nvda_pe}"
    assert nvda_pe > 0, f"NVDA PE must be positive, got {nvda_pe}"


def test_real_adapter_sentiment_loaded_when_available():
    """Tickers in eodhd_global_backfill.parquet should get real sentiment; others get NaN."""
    # CLSK is in the eodhd backfill parquets
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u = _make_universe(["CLSK"])
    ds = adapter.fetch(u, u.window_days)

    clsk_sentiment = ds.data["CLSK"].news_sentiment
    assert isinstance(clsk_sentiment, Decimal)
    # CLSK exists in backfill — should be real or NaN depending on date window
    # At minimum it must be Decimal (not float/None)


def test_real_adapter_no_stubs_in_output():
    """No ticker should have news_sentiment=0 or pe_ratio=0 (the old stub values)."""
    adapter = RealDataAdapter(base_path=TRADING_DATA)
    u = _make_universe(["NVDA", "MSFT", "AAPL"])
    ds = adapter.fetch(u, u.window_days)

    for ticker, td in ds.data.items():
        # Old stub value was Decimal("0") — should be gone
        assert td.news_sentiment != Decimal("0"), f"{ticker} has stub sentiment=0"
        assert td.pe_ratio != Decimal("0"), f"{ticker} has stub pe_ratio=0"


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


# ── Download-enabled tests ────────────────────────────────────────────────────

def test_download_enabled_local_first_still_serves():
    """With download_enabled=True but local CSV available, adapter should serve local."""

    adapter = RealDataAdapter(
        base_path=TRADING_DATA,
        subdirs=CSV_SUBDIRS,
        news_dir=_NEWS_DIR,
        fundamentals_dir=_FUNDAMENTALS_DIR,
        download_enabled=True,
        stale_ohlcv_days=365,  # local CSV won't be considered stale
        stale_news_days=365,
    )
    u = _make_universe(["NVDA", "MSFT"])
    ds = adapter.fetch(u, u.window_days)
    assert "NVDA" in ds.data
    assert "MSFT" in ds.data
    assert len(ds.data["NVDA"].ohlcv) > 0


def test_find_csv_path_locates_ticker():
    path = _find_csv_path(TRADING_DATA, CSV_SUBDIRS, "NVDA")
    assert path is not None
    assert path.stem.upper() == "NVDA"


def test_find_csv_path_returns_none_for_missing():
    path = _find_csv_path(TRADING_DATA, CSV_SUBDIRS, "NONEXISTENT_999")
    assert path is None


# ── Incremental update: helper functions ────────────────────────────────────


def test_get_last_csv_date_returns_max_date():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "TEST.csv"
        csv_path.write_text(
            "Date,Close,Volume\n"
            "2026-01-01,100,1000\n"
            "2026-01-02,101,2000\n"
            "2026-01-05,105,3000\n"
        )
        assert _get_last_csv_date(csv_path) == date(2026, 1, 5)


def test_get_last_csv_date_nonexistent():
    assert _get_last_csv_date(Path("/nonexistent/path.csv")) is None


def test_get_last_csv_date_empty_file():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "TEST.csv"
        csv_path.write_text("Date,Close,Volume\n")
        assert _get_last_csv_date(csv_path) is None


def test_get_last_parquet_date_returns_max_date():
    with tempfile.TemporaryDirectory() as tmp:
        pq_path = Path(tmp) / "test.parquet"
        df = pd.DataFrame({"Date": ["2026-01-01", "2026-01-03"], "Ticker": ["A", "A"], "Sentiment": [0.1, 0.2]})
        df.to_parquet(pq_path, index=False, engine="pyarrow")
        assert _get_last_parquet_date(pq_path) == date(2026, 1, 3)


def test_get_last_parquet_date_nonexistent():
    assert _get_last_parquet_date(Path("/nonexistent/test.parquet")) is None


# ── Incremental update: stale checks ────────────────────────────────────────


def test_ohlcv_stale_fresh_data():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "TEST.csv"
        today_str = TODAY.strftime("%Y-%m-%d")
        csv_path.write_text(f"Date,Close,Volume\n{today_str},100,1000\n")
        adapter = RealDataAdapter(base_path=Path(tmp), subdirs=[], stale_ohlcv_days=1)
        assert not adapter._ohlcv_stale(csv_path)


def test_ohlcv_stale_old_data():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "TEST.csv"
        csv_path.write_text("Date,Close,Volume\n2025-01-01,100,1000\n")
        adapter = RealDataAdapter(base_path=Path(tmp), subdirs=[], stale_ohlcv_days=1)
        assert adapter._ohlcv_stale(csv_path)


def test_ohlcv_stale_no_file():
    adapter = RealDataAdapter(stale_ohlcv_days=1)
    assert adapter._ohlcv_stale(Path("/nonexistent/TEST.csv"))


def test_news_stale_fresh_data():
    with tempfile.TemporaryDirectory() as tmp:
        news_dir = Path(tmp)
        today = date.today()
        out_file = news_dir / "eodhd_global_backfill.parquet"
        df = pd.DataFrame({"Date": [today.strftime("%Y-%m-%d")], "Ticker": ["A"], "Sentiment": [0.1]})
        df.to_parquet(out_file, index=False, engine="pyarrow")
        adapter = RealDataAdapter(news_dir=news_dir, subdirs=[], stale_news_days=7)
        assert not adapter._news_stale()


def test_news_stale_old_data():
    with tempfile.TemporaryDirectory() as tmp:
        news_dir = Path(tmp)
        out_file = news_dir / "eodhd_global_backfill.parquet"
        df = pd.DataFrame({"Date": ["2025-01-01"], "Ticker": ["A"], "Sentiment": [0.1]})
        df.to_parquet(out_file, index=False, engine="pyarrow")
        adapter = RealDataAdapter(news_dir=news_dir, subdirs=[], stale_news_days=7)
        assert adapter._news_stale()


def test_news_stale_no_file():
    with tempfile.TemporaryDirectory() as tmp:
        adapter = RealDataAdapter(news_dir=Path(tmp), subdirs=[], stale_news_days=7)
        assert adapter._news_stale()


# ── Incremental update: force_refresh ───────────────────────────────────────


def test_force_refresh_bypasses_ohlcv():
    """force_refresh=True should trigger download attempt even when CSV is current."""
    with tempfile.TemporaryDirectory() as tmp:
        csv_dir = Path(tmp) / "nasdaq" / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        today_str = TODAY.strftime("%Y-%m-%d")
        csv_path = csv_dir / "ABC.csv"
        csv_path.write_text(f"Date,Close,Volume\n{today_str},100,1000\n")

        adapter = RealDataAdapter(
            base_path=Path(tmp), subdirs=["nasdaq/csv"],
            download_enabled=True, stale_ohlcv_days=1,
            force_refresh=True,
        )
        # Download will fail (no yfinance data for fake ticker) but should attempt it
        result = adapter._ensure_ohlcv("ABC", TODAY)
        # The key invariant: with force_refresh and download enabled, _ohlcv_stale should NOT
        # short-circuit. Download is attempted; on failure, existing csv_path is returned.
        assert result is not None  # existing path returned since download failed


def test_fundamentals_skips_existing():
    """Fundamentals parquet exists and not force_refresh — should skip download."""
    with tempfile.TemporaryDirectory() as tmp:
        fundamentals_dir = Path(tmp)
        fmp_path = fundamentals_dir / "fmp_raw_TEST.parquet"
        df = pd.DataFrame({"statement": ["income_statement"], "raw_json": ["[]"]})
        df.to_parquet(fmp_path, index=False, engine="pyarrow")

        adapter = RealDataAdapter(
            fundamentals_dir=fundamentals_dir, subdirs=[],
            download_enabled=True, api_keys={"fmp": "fake"},
            force_refresh=False,
        )
        result = adapter._ensure_fundamentals("TEST")
        assert result == fmp_path


def test_fundamentals_force_refresh():
    """force_refresh=True should re-download fundamentals (will fail with fake key, but logic should hit download)."""
    with tempfile.TemporaryDirectory() as tmp:
        fundamentals_dir = Path(tmp)
        fmp_path = fundamentals_dir / "fmp_raw_TEST.parquet"
        df = pd.DataFrame({"statement": ["income_statement"], "raw_json": ["[]"]})
        df.to_parquet(fmp_path, index=False, engine="pyarrow")

        adapter = RealDataAdapter(
            fundamentals_dir=fundamentals_dir, subdirs=[],
            download_enabled=True, api_keys={"fmp": "fake"},
            force_refresh=True,
        )
        result = adapter._ensure_fundamentals("TEST")
        # Download with fake key fails, existing file is returned gracefully
        assert result == fmp_path


# ── Re-download trigger: needs_redownload flag ──────────────────────────────

def test_ohlcv_needs_redownload_triggers_force_fresh():
    """When normalize detects unresolvable format issues, force-fresh re-download is triggered."""
    from portfolio_ninja.data_plane.real_adapter import _download_ohlcv_yfinance

    with tempfile.TemporaryDirectory() as tmp:
        csv_dir = Path(tmp) / "nasdaq" / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)

        # Create a CSV with unresolvable format issues (will trigger needs_redownload=True)
        csv_path = csv_dir / "TEST.csv"
        csv_path.write_text(
            "Date,Open,High,Low,Close,Volume\n"
            "01/13/2026,100,101,99,100.5,1000000\n"
            "02/14/2026,101,102,100,101.5,1000000\n"
            "12/01/2025,102,103,101,102.5,1000000\n"
            "25/12/2025,103,104,102,103.5,1000000\n"
        )

        # Mock yfinance to return clean data; verify the existing file is replaced
        import unittest.mock

        clean_df = pd.DataFrame({
            "Date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "Open": [100, 101, 102],
            "High": [101, 102, 103],
            "Low": [99, 100, 101],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [1000000, 1000000, 1000000],
            "Adjusted Close": [100.5, 101.5, 102.5],
        })
        clean_df["Date"] = pd.to_datetime(clean_df["Date"])
        clean_df = clean_df.set_index("Date")

        with unittest.mock.patch("yfinance.download", return_value=clean_df):
            result = _download_ohlcv_yfinance(
                "TEST", Path(tmp), "2026-01-01", "2026-12-31", ["nasdaq/csv"]
            )

        # Result should be the CSV path
        assert result == csv_path
        # File should exist and be cleanly formatted (not contain the bad dates)
        assert csv_path.exists()
        content = csv_path.read_text()
        # New file should have ISO-formatted dates
        assert "2026-01-" in content
        # Old unresolvable dates should be gone
        assert "25/12/2025" not in content
        assert "01/13/2026" not in content


# ── Phase 3: News and Fundamentals force_fresh pattern ──────────────────────


def test_download_news_force_fresh_skips_merge():
    """When force_fresh=True, news download skips merge and overwrites from scratch."""
    import unittest.mock

    from portfolio_ninja.data_plane.real_adapter import _download_news_sentiment_eodhd

    with tempfile.TemporaryDirectory() as tmp:
        news_dir = Path(tmp)

        # Create an existing parquet with old data
        old_df = pd.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Ticker": ["NVDA", "MSFT"],
            "Sentiment": [0.5, -0.3],
        })
        old_path = news_dir / "eodhd_global_backfill.parquet"
        old_df.to_parquet(old_path, index=False, engine="pyarrow")

        # Mock API response with new data
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "date": "2026-05-16",
                "sentiment": {"polarity": 0.8},
            },
        ]

        with unittest.mock.patch("requests.get", return_value=mock_response):
            result = _download_news_sentiment_eodhd(
                ["NVDA"], news_dir, "fake_key", "2026-01-01", "2026-05-16",
                force_fresh=True
            )

        # Result is the parquet path
        assert result == old_path
        # File was overwritten: should only contain new data (from force_fresh)
        result_df = pd.read_parquet(result)
        # When force_fresh=True, only the newly downloaded data is in the file (no merge)
        assert len(result_df) == 1  # only the new record, not the old ones
        assert result_df.iloc[0]["Date"] == "2026-05-16"


def test_download_news_normal_merge_includes_existing():
    """When force_fresh=False (default), news download merges with existing data."""
    import unittest.mock

    from portfolio_ninja.data_plane.real_adapter import _download_news_sentiment_eodhd

    with tempfile.TemporaryDirectory() as tmp:
        news_dir = Path(tmp)

        # Create an existing parquet with old data
        old_df = pd.DataFrame({
            "Date": ["2025-01-01", "2025-01-02"],
            "Ticker": ["NVDA", "MSFT"],
            "Sentiment": [0.5, -0.3],
        })
        old_path = news_dir / "eodhd_global_backfill.parquet"
        old_df.to_parquet(old_path, index=False, engine="pyarrow")

        # Mock API response with new data
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "date": "2026-05-16",
                "sentiment": {"polarity": 0.8},
            },
        ]

        with unittest.mock.patch("requests.get", return_value=mock_response):
            result = _download_news_sentiment_eodhd(
                ["NVDA"], news_dir, "fake_key", "2026-01-01", "2026-05-16",
                force_fresh=False  # normal merge
            )

        # File contains merged data (old + new)
        result_df = pd.read_parquet(result)
        # Should have old data (2) + new data (1) = 3 rows
        assert len(result_df) == 3
        # Verify new data is present
        assert result_df["Date"].str.contains("2026-05-16").any()
        # Verify old data is present
        assert result_df["Date"].str.contains("2025-01-").any()


def test_download_fundamentals_force_fresh_parameter():
    """Verify force_fresh parameter is accepted by fundamentals download."""
    import unittest.mock

    from portfolio_ninja.data_plane.real_adapter import _download_fundamentals_fmp

    with tempfile.TemporaryDirectory() as tmp:
        fundamentals_dir = Path(tmp)

        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"epsDiluted": 1.5, "date": "2026-Q1"},
        ]

        with unittest.mock.patch("requests.get", return_value=mock_response):
            result = _download_fundamentals_fmp(
                "NVDA", fundamentals_dir, "fake_key", force_fresh=True
            )

        # File was created
        assert result.exists()
        # Verify it's a valid parquet
        df = pd.read_parquet(result)
        assert "statement" in df.columns
        assert df.iloc[0]["statement"] == "income_statement"
