import pytest
from datetime import date
from decimal import Decimal

from portfolio_ninja.domain.objects import RunConfig, Universe
from portfolio_ninja.domain.stubs import StubDataAdapter
from portfolio_ninja.domain.exceptions import DataUnavailableError
from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.universe_gateway import create_universe

TODAY = date(2026, 1, 15)
VALID_CONFIG = RunConfig(tickers=["AAPL", "MSFT"], run_mode="backtest", window_days=30)


def _make_universe() -> Universe:
    return create_universe(VALID_CONFIG, as_of_date=TODAY)


def test_data_plane_valid_universe_returns_complete_market_dataset():
    u = _make_universe()
    ds = fetch_market_data(u, StubDataAdapter())
    assert ds.validation_status == "valid"
    assert ds.as_of_date == TODAY
    assert ds.params_hash != ""
    assert ds.source_data_version != ""


def test_data_plane_stub_adapter_produces_entry_for_every_ticker():
    u = _make_universe()
    ds = fetch_market_data(u, StubDataAdapter())
    assert set(ds.data.keys()) == {"AAPL", "MSFT"}


def test_data_plane_missing_ticker_in_adapter_response_raises_data_unavailable_error():
    class PartialAdapter(StubDataAdapter):
        def fetch(self, universe, window_days):
            result = super().fetch(universe, window_days)
            # Remove one ticker from the response
            reduced = {k: v for k, v in result.data.items() if k != "MSFT"}
            from portfolio_ninja.domain.objects import MarketDataset
            return MarketDataset(
                data=reduced,
                source_data_version=result.source_data_version,
                as_of_date=result.as_of_date,
                params_hash=result.params_hash,
            )

    u = _make_universe()
    with pytest.raises(DataUnavailableError, match="Missing tickers"):
        fetch_market_data(u, PartialAdapter())


def test_data_plane_adapter_exception_propagates_as_data_unavailable_error():
    from portfolio_ninja.domain.adapters import DataAdapter

    class FailingAdapter(DataAdapter):
        def fetch(self, universe, window_days):
            raise RuntimeError("network timeout")

    u = _make_universe()
    with pytest.raises(DataUnavailableError, match="network timeout"):
        fetch_market_data(u, FailingAdapter())


def test_data_plane_all_price_fields_are_decimal():
    u = _make_universe()
    ds = fetch_market_data(u, StubDataAdapter())
    for ticker_data in ds.data.values():
        for bar in ticker_data.ohlcv:
            assert isinstance(bar.open, Decimal)
            assert isinstance(bar.high, Decimal)
            assert isinstance(bar.low, Decimal)
            assert isinstance(bar.close, Decimal)
        assert isinstance(ticker_data.news_sentiment, Decimal)
        assert isinstance(ticker_data.pe_ratio, Decimal)


def test_data_plane_source_data_version_is_non_empty():
    u = _make_universe()
    ds = fetch_market_data(u, StubDataAdapter())
    assert ds.source_data_version != ""


def test_data_plane_validation_status_is_valid_on_success():
    u = _make_universe()
    ds = fetch_market_data(u, StubDataAdapter())
    assert ds.validation_status == "valid"


def test_data_plane_integration_stub_adapter_deterministic_for_same_inputs():
    u = _make_universe()
    ds1 = fetch_market_data(u, StubDataAdapter())
    ds2 = fetch_market_data(u, StubDataAdapter())
    assert ds1.params_hash == ds2.params_hash
    assert ds1.source_data_version == ds2.source_data_version
    for ticker in ds1.data:
        assert ds1.data[ticker].news_sentiment == ds2.data[ticker].news_sentiment
        assert ds1.data[ticker].pe_ratio == ds2.data[ticker].pe_ratio
