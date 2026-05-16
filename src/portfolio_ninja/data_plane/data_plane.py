import hashlib

from portfolio_ninja.domain.adapters import DataAdapter
from portfolio_ninja.domain.exceptions import DataIntegrityError, DataUnavailableError
from portfolio_ninja.domain.objects import MarketDataset, Universe


def fetch_market_data(universe: Universe, adapter: DataAdapter) -> MarketDataset:
    try:
        dataset = adapter.fetch(universe, universe.window_days)
    except Exception as exc:
        raise DataUnavailableError(str(exc)) from exc

    missing = set(universe.tickers) - set(dataset.data.keys())
    if missing:
        raise DataUnavailableError(f"Missing tickers: {sorted(missing)}")

    for ticker, ticker_data in dataset.data.items():
        if not ticker_data.ohlcv:
            raise DataUnavailableError(f"Empty OHLCV for ticker {ticker}")
        for bar in ticker_data.ohlcv:
            if bar.high < bar.low:
                raise DataIntegrityError(
                    f"OHLCVBar integrity violation: high < low for {ticker} on {bar.date}"
                )

    regime_data: dict = {}
    for ticker in universe.regime_tickers:
        try:
            regime_u = Universe(
                tickers=[ticker],
                run_mode=universe.run_mode,
                window_days=universe.window_days,
                as_of_date=universe.as_of_date,
                params_hash=hashlib.sha256(
                    f"{universe.params_hash}|regime|{ticker}".encode()
                ).hexdigest(),
            )
            regime_ds = adapter.fetch(regime_u, universe.window_days)
            if ticker in regime_ds.data:
                regime_data[ticker] = regime_ds.data[ticker]
        except Exception:
            pass

    params_hash = hashlib.sha256(
        f"{universe.params_hash}|{dataset.source_data_version}".encode()
    ).hexdigest()

    return MarketDataset(
        data=dataset.data,
        source_data_version=dataset.source_data_version,
        as_of_date=universe.as_of_date,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=[],
        regime_data=regime_data,
    )
