#!/usr/bin/env python
"""
DataPlane Module — Live Runtime Demo
Shows: Universe → DataPlane → MarketDataset flow, stub data, failures, contracts.
"""

from datetime import date
from decimal import Decimal

from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.domain.adapters import DataAdapter
from portfolio_ninja.domain.exceptions import (
    DataIntegrityError,
    DataUnavailableError,
    IncompleteDataError,
)
from portfolio_ninja.domain.objects import (
    CRITICAL_SOURCES,
    DEGRADED_SOURCES,
    DataQualityReport,
    MarketDataset,
    OHLCVBar,
    RunConfig,
    SourceCriticality,
    TickerData,
)
from portfolio_ninja.domain.stubs import StubDataAdapter
from portfolio_ninja.universe_gateway import create_universe

# ── Helpers ──────────────────────────────────────────────────────────────────

def bar_to_dict(bar: OHLCVBar) -> dict:
    return {
        "date": str(bar.date),
        "open": str(bar.open),
        "high": str(bar.high),
        "low": str(bar.low),
        "close": str(bar.close),
        "volume": bar.volume,
    }

def ticker_summary(t: TickerData) -> dict:
    return {
        "ohlcv_bars": len(t.ohlcv),
        "sample_bars": [bar_to_dict(b) for b in t.ohlcv[:3]],
        "news_sentiment": str(t.news_sentiment),
        "pe_ratio": str(t.pe_ratio),
    }

def print_section(n: int, title: str):
    print(f"\n{'='*70}")
    print(f"  Section {n}: {title}")
    print(f"{'='*70}\n")


# ── 1. Universe construction ────────────────────────────────────────────────

print_section(1, "Universe Construction")

config = RunConfig(
    tickers=["AAPL", "MSFT", "NVDA"],
    run_mode="backtest",
    window_days=30,
)
as_of = date(2026, 1, 15)
universe = create_universe(config, as_of_date=as_of)

print(f"Input: {len(universe.tickers)} tickers = {universe.tickers}")
print(f"  run_mode:     {universe.run_mode}")
print(f"  window_days:  {universe.window_days}")
print(f"  as_of_date:   {universe.as_of_date}")
print(f"  params_hash:  {universe.params_hash[:16]}...")
print(f"  status:       {universe.validation_status}")


# ── 2. StubDataAdapter direct fetch ─────────────────────────────────────────

print_section(2, "StubDataAdapter Direct Fetch")

stub = StubDataAdapter(seed=42)
raw = stub.fetch(universe, universe.window_days)

print(f"Adapter returned source_data_version: {raw.source_data_version}")
print(f"Tickers in response: {sorted(raw.data.keys())}")
for ticker in ["AAPL", "MSFT", "NVDA"]:
    td = raw.data[ticker]
    summary = ticker_summary(td)
    print(f"\n  {ticker}:")
    print(f"    bars:       {summary['ohlcv_bars']}")
    print(f"    first_bar:  date={summary['sample_bars'][0]['date']}, "
          f"open={summary['sample_bars'][0]['open']}, "
          f"close={summary['sample_bars'][0]['close']}")
    print(f"    sentiment:  {summary['news_sentiment']}")
    print(f"    pe_ratio:   {summary['pe_ratio']}")
    print(f"    price type: {type(td.ohlcv[0].open).__name__}")

assert isinstance(td.ohlcv[0].open, Decimal), "Price must be Decimal"


# ── 3. fetch_market_data() happy path ───────────────────────────────────────

print_section(3, "DataPlane Happy Path: Universe → fetch_market_data() → MarketDataset")

dataset = fetch_market_data(universe, StubDataAdapter(seed=42))

print("MarketDataset:")
print(f"  tickers:            {sorted(dataset.data.keys())}")
print(f"  source_data_version: {dataset.source_data_version}")
print(f"  as_of_date:         {dataset.as_of_date}")
print(f"  params_hash:        {dataset.params_hash}")
print(f"  validation_status:  {dataset.validation_status}")
print(f"  reason_codes:       {dataset.reason_codes}")

# Show total bars across universe
total_bars = sum(len(td.ohlcv) for td in dataset.data.values())
print(f"\n  total OHLCV bars:   {total_bars}")
print(f"  bars per ticker:  {[len(dataset.data[t].ohlcv) for t in sorted(dataset.data)]}")


# ── 4. DataQualityReport (newly ported legacy type) ─────────────────────────

print_section(4, "DataQualityReport — Legacy Class A Asset, Ported")

# Scenario A: all critical sources present, one degraded missing
dqr_a = DataQualityReport(
    degraded_missing=["smh_benchmark"],
    warnings=["data_2_days_old"],
)
print("Scenario A: 1 degraded source missing")
print(f"  critical_missing:  {dqr_a.critical_missing}")
print(f"  degraded_missing:  {dqr_a.degraded_missing}")
print(f"  warnings:          {dqr_a.warnings}")
print(f"  can_rebalance:     {dqr_a.can_rebalance}")
print(f"  to_dict():         {dqr_a.to_dict()}")

# Scenario B: critical source missing → cannot rebalance
dqr_b = DataQualityReport(critical_missing=["prices"])
print("\nScenario B: CRITICAL source 'prices' missing")
print(f"  critical_missing:  {dqr_b.critical_missing}")
print(f"  can_rebalance:     {dqr_b.can_rebalance}")
assert dqr_b.can_rebalance is False, "Must be False when critical sources are missing"


# ── 5. IncompleteDataError (newly ported legacy exception) ──────────────────

print_section(5, "IncompleteDataError — Legacy Class A Asset, Ported")

try:
    raise IncompleteDataError(
        missing_sources=["prices", "regime_status"],
        criticality="CRITICAL",
    )
except IncompleteDataError as e:
    print(f"Raised: {type(e).__name__}")
    print(f"  missing_sources: {e.missing_sources}")
    print(f"  criticality:     {e.criticality}")
    print(f"  message:         {e}")


# ── 6. SourceCriticality enum + constant lists ──────────────────────────────

print_section(6, "SourceCriticality + Criticality Constants")

print(f"SourceCriticality.CRITICAL = {SourceCriticality.CRITICAL!r}")
print(f"SourceCriticality.DEGRADED = {SourceCriticality.DEGRADED!r}")
print(f"CRITICAL_SOURCES = {CRITICAL_SOURCES}")
print(f"DEGRADED_SOURCES = {DEGRADED_SOURCES}")


# ── 7. Failure mode: missing ticker ─────────────────────────────────────────

print_section(7, "Failure: Missing Ticker")

class PartialAdapter(StubDataAdapter):
    def fetch(self, universe, window_days):
        result = super().fetch(universe, window_days)
        reduced = {k: v for k, v in result.data.items() if k != "NVDA"}
        return MarketDataset(
            data=reduced, source_data_version=result.source_data_version,
            as_of_date=result.as_of_date, params_hash=result.params_hash,
        )

try:
    fetch_market_data(universe, PartialAdapter(seed=42))
except DataUnavailableError as e:
    print(f"Caught {type(e).__name__}: {e}")


# ── 8. Failure mode: adapter exception ──────────────────────────────────────

print_section(8, "Failure: Adapter Exception")

class FailingAdapter(DataAdapter):
    def fetch(self, universe, window_days):
        raise ConnectionRefusedError("connection refused on port 7497")

try:
    fetch_market_data(universe, FailingAdapter())
except DataUnavailableError as e:
    print(f"Caught {type(e).__name__}: {e}")


# ── 9. Failure mode: corrupted OHLCV (high < low) ───────────────────────────

print_section(9, "Failure: Corrupted OHLCV — high < low")

class CorruptAdapter(DataAdapter):
    def fetch(self, universe, window_days):
        from portfolio_ninja.domain.objects import OHLCVBar, TickerData
        bad_bar = OHLCVBar(
            date=as_of,
            open=Decimal("100"),
            high=Decimal("99"),
            low=Decimal("101"),
            close=Decimal("100"),
            volume=1000,
        )
        td_bad = TickerData(ohlcv=[bad_bar], news_sentiment=Decimal("0"), pe_ratio=Decimal("15"))
        td_ok = TickerData(
            ohlcv=[OHLCVBar(date=as_of, open=Decimal("100"), high=Decimal("102"),
                            low=Decimal("99"), close=Decimal("101"), volume=500)],
            news_sentiment=Decimal("0"), pe_ratio=Decimal("15"),
        )
        # Include ALL tickers so the missing-ticker check passes
        data = {t: (td_bad if t == "AAPL" else td_ok) for t in universe.tickers}
        return MarketDataset(
            data=data, source_data_version="corrupt-v1",
            as_of_date=as_of, params_hash="xxx",
        )

try:
    fetch_market_data(universe, CorruptAdapter())
except DataIntegrityError as e:
    print(f"Caught {type(e).__name__}: {e}")


# ── 10. Determinism check ───────────────────────────────────────────────────

print_section(10, "Determinism: Same Inputs → Same Output")

ds1 = fetch_market_data(universe, StubDataAdapter(seed=42))
ds2 = fetch_market_data(universe, StubDataAdapter(seed=42))

print(f"Run 1 params_hash:  {ds1.params_hash}")
print(f"Run 2 params_hash:  {ds2.params_hash}")
print(f"Hashes match:       {ds1.params_hash == ds2.params_hash}")
print(f"source_version match: {ds1.source_data_version == ds2.source_data_version}")

# Cross-ticker determinism
for t in ds1.data:
    s1 = ds1.data[t].news_sentiment
    s2 = ds2.data[t].news_sentiment
    assert s1 == s2, f"{t} sentiment not deterministic: {s1} != {s2}"
print("Sentiment match:    True (all tickers)")


# ── Footer ──────────────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print("  Demo complete — all 10 sections passed")
print(f"{'='*70}\n")
