from __future__ import annotations

import hashlib
import logging
import random
from datetime import timedelta
from decimal import Decimal

from .adapters import DataAdapter, ExecutionAdapter
from .objects import (
    ExecutionIntent,
    MarketDataset,
    OHLCVBar,
    TickerData,
    Universe,
)

logger = logging.getLogger(__name__)

_STUB_VERSION = "stub-v1-seed42"


class StubDataAdapter(DataAdapter):
    def __init__(self, seed: int = 42) -> None:
        self._seed = seed

    def fetch(self, universe: Universe, window_days: int) -> MarketDataset:
        data: dict[str, TickerData] = {}
        as_of = universe.as_of_date
        for ticker in universe.tickers:
            ticker_seed = self._seed + abs(hash(ticker)) % 10000
            trng = random.Random(ticker_seed)
            bars: list[OHLCVBar] = []
            n_bars = min(30, window_days)
            base_price = Decimal(str(round(50 + trng.random() * 150, 2)))
            for i in range(n_bars, 0, -1):
                bar_date = as_of - timedelta(days=i)
                price_delta = Decimal(str(round((trng.random() - 0.5) * 4, 2)))
                open_p = base_price + price_delta
                close_p = open_p + Decimal(str(round((trng.random() - 0.5) * 2, 2)))
                high_p = max(open_p, close_p) + Decimal(str(round(trng.random(), 2)))
                low_p = min(open_p, close_p) - Decimal(str(round(trng.random(), 2)))
                volume = int(trng.random() * 1_000_000) + 100_000
                bars.append(OHLCVBar(
                    date=bar_date,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=volume,
                ))
                base_price = close_p
            news_sentiment = Decimal(str(round(trng.random() * 2 - 1, 4)))
            pe_ratio = Decimal(str(round(10 + trng.random() * 30, 2)))
            data[ticker] = TickerData(
                ohlcv=bars,
                news_sentiment=news_sentiment,
                pe_ratio=pe_ratio,
            )
        params_input = f"{universe.params_hash}|{window_days}|{_STUB_VERSION}"
        params_hash = hashlib.sha256(params_input.encode()).hexdigest()
        return MarketDataset(
            data=data,
            source_data_version=_STUB_VERSION,
            as_of_date=as_of,
            params_hash=params_hash,
        )


class StubExecutionAdapter(ExecutionAdapter):
    def submit(self, intent: ExecutionIntent) -> None:
        logger.info(
            "StubExecutionAdapter: run_mode=%s adapter_id=%s orders=%d params_hash=%s",
            intent.run_mode,
            intent.adapter_id,
            len(intent.orders),
            intent.params_hash,
        )
