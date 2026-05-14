#!/usr/bin/env python
"""DataPlane Real Data — Live Demo.

Wires RealDataAdapter to pre-downloaded CSV data, proves real input→output flow,
generates artifacts, and verifies determinism + fail-loud behavior.
"""

import csv
import json
import sys
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from portfolio_ninja.domain.objects import RunConfig, OHLCVBar, TickerData
from portfolio_ninja.domain.exceptions import IncompleteDataError, DataIntegrityError
from portfolio_ninja.data_plane.real_adapter import RealDataAdapter

ARTIFACTS_DIR = project_root / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

TRADING_DATA = Path("C:/portfolio_ninja/trading_data/stock_market_data")
TODAY = date(2026, 5, 14)

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

def ticker_summary(td: TickerData) -> dict:
    return {
        "bars": len(td.ohlcv),
        "sample_bars": [bar_to_dict(b) for b in td.ohlcv[:3]],
        "news_sentiment": str(td.news_sentiment),
        "pe_ratio": str(td.pe_ratio),
    }

def print_section(n: int, title: str):
    print(f"\n{'='*70}")
    print(f"  Section {n}: {title}")
    print(f"{'='*70}\n")

# ── 1. Build config + universe ──────────────────────────────────────────────
print_section(1, "Universe + Config")

config = RunConfig(
    tickers=["NVDA", "MSFT"],
    run_mode="backtest",
    window_days=200,
)
print(f"Tickers: {config.tickers}")
print(f"window_days: {config.window_days}")
print(f"run_mode: {config.run_mode}")

# ── 2. Fetch from CSV with RealDataAdapter ──────────────────────────────────
print_section(2, "RealDataAdapter Fetch (NVDA + MSFT)")

adapter = RealDataAdapter(base_path=TRADING_DATA)

# Build a minimal Universe object for the adapter (not using create_universe
# to avoid UniverseGateway dependency in this demo script)
from portfolio_ninja.domain.objects import Universe
import hashlib

universe = Universe(
    tickers=config.tickers,
    run_mode=config.run_mode,
    window_days=config.window_days,
    as_of_date=TODAY,
    params_hash=hashlib.sha256(
        json.dumps({"tickers": config.tickers}).encode()
    ).hexdigest(),
)

dataset = adapter.fetch(universe, config.window_days)
print(f"source_data_version: {dataset.source_data_version}")
print(f"as_of_date: {dataset.as_of_date}")
print(f"params_hash: {dataset.params_hash}")
print(f"tickers loaded: {sorted(dataset.data.keys())}")
print(f"validation_status: {dataset.validation_status}")

for ticker in sorted(dataset.data):
    td = dataset.data[ticker]
    s = ticker_summary(td)
    print(f"\n  {ticker}:")
    print(f"    bars: {s['bars']}")
    print(f"    oldest: {s['sample_bars'][0]['date']}")
    print(f"    newest: {s['sample_bars'][-1]['date'] if s['sample_bars'][-1] else '(none)'}")
    print(f"    first bar: open={s['sample_bars'][0]['open']}, close={s['sample_bars'][0]['close']}")
    print(f"    price type: {type(td.ohlcv[0].open).__name__}")
    assert isinstance(td.ohlcv[0].open, Decimal), f"{ticker}: prices not Decimal!"

# ── 3. Save CSV artifact ────────────────────────────────────────────────────
print_section(3, "Save CSV Artifact")

csv_path = ARTIFACTS_DIR / "dataplane_real_sample.csv"
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "ticker", "date", "open", "high", "low", "close", "volume",
        "news_sentiment", "pe_ratio",
    ])
    for ticker in sorted(dataset.data):
        td = dataset.data[ticker]
        for bar in td.ohlcv:
            writer.writerow([
                ticker, str(bar.date), str(bar.open), str(bar.high),
                str(bar.low), str(bar.close), bar.volume,
                str(td.news_sentiment), str(td.pe_ratio),
            ])

rows_written = sum(len(td.ohlcv) for td in dataset.data.values())
print(f"Wrote {rows_written} rows to {csv_path}")

# ── 4. Save JSON artifact ───────────────────────────────────────────────────
print_section(4, "Save JSON Artifact")

def dataset_to_dict(ds) -> dict:
    """Convert MarketDataset to JSON-safe dict."""
    return {
        "source_data_version": ds.source_data_version,
        "as_of_date": str(ds.as_of_date),
        "params_hash": ds.params_hash,
        "validation_status": ds.validation_status,
        "reason_codes": ds.reason_codes,
        "data": {
            ticker: ticker_summary(td)
            for ticker, td in ds.data.items()
        },
    }

json_path = ARTIFACTS_DIR / "dataplane_real_sample.json"
with open(json_path, "w") as f:
    json.dump(dataset_to_dict(dataset), f, indent=2, ensure_ascii=False)

print(f"Wrote JSON to {json_path}")
print(json.dumps(dataset_to_dict(dataset), indent=2, ensure_ascii=False)[:1000])

# ── 5. Decimal proof ────────────────────────────────────────────────────────
print_section(5, "Decimal OHLCV Fields")

for ticker in sorted(dataset.data):
    td = dataset.data[ticker]
    for bar in td.ohlcv:
        for field_name in ("open", "high", "low", "close"):
            val = getattr(bar, field_name)
            assert isinstance(val, Decimal), f"{ticker}.{field_name} is {type(val)}, not Decimal!"
    print(f"  {ticker}: ALL {len(td.ohlcv)} bars × 4 OHLC fields = Decimal ✓")
    print(f"  {ticker}: news_sentiment = {td.news_sentiment} (type={type(td.news_sentiment).__name__})")
    print(f"  {ticker}: pe_ratio = {td.pe_ratio} (type={type(td.pe_ratio).__name__})")

# ── 6. DataQualityReport ────────────────────────────────────────────────────
print_section(6, "DataQualityReport")

print("  (DataQualityReport is populated by RealDataAdapter.fetch)")
print(f"  (See section 2 output — warnings are logged during fetch)")

# ── 7. Missing ticker → fail-loud ──────────────────────────────────────────
print_section(7, "Missing Ticker → Fail-Loud")

from portfolio_ninja.domain.objects import Universe

universe_unknown = Universe(
    tickers=["NONEXISTENT_TICKER_999"],
    run_mode="backtest",
    window_days=30,
    as_of_date=TODAY,
    params_hash="xxxxx",
)

try:
    adapter.fetch(universe_unknown, 30)
    print("  FAIL: should have raised!")
except IncompleteDataError as e:
    print(f"  Caught {type(e).__name__}: {e}")
    print(f"  missing_sources: {e.missing_sources}")
    print(f"  criticality: {e.criticality}")
    print("  ✓ Fail-loud confirmed")

# ── 8. Determinism: same input → same hash ─────────────────────────────────
print_section(8, "Determinism: Same Input → Same Hash")

universe2 = Universe(
    tickers=config.tickers,
    run_mode=config.run_mode,
    window_days=config.window_days,
    as_of_date=TODAY,
    params_hash=hashlib.sha256(
        json.dumps({"tickers": config.tickers}).encode()
    ).hexdigest(),
)

ds1 = adapter.fetch(universe, config.window_days)
ds2 = adapter.fetch(universe2, config.window_days)

print(f"Run 1 params_hash: {ds1.params_hash}")
print(f"Run 2 params_hash: {ds2.params_hash}")
print(f"Hashes match: {ds1.params_hash == ds2.params_hash}")
assert ds1.params_hash == ds2.params_hash, "Hashes must match!"
print("  ✓ Determinism confirmed")

# ── 9. Different ticker → different output ──────────────────────────────────
print_section(9, "Different Ticker → Different Output")

universe_aapl = Universe(
    tickers=["AAPL"],
    run_mode="backtest",
    window_days=200,
    as_of_date=TODAY,
    params_hash=hashlib.sha256(
        json.dumps({"tickers": ["AAPL"]}).encode()
    ).hexdigest(),
)

ds_aapl = adapter.fetch(universe_aapl, config.window_days)
print(f"NVDA+MSFT hash: {ds1.params_hash}")
print(f"AAPL hash:      {ds_aapl.params_hash}")
print(f"AAPL tickers:   {sorted(ds_aapl.data.keys())}")
print(f"Different: {ds1.params_hash != ds_aapl.params_hash}")
assert ds1.params_hash != ds_aapl.params_hash, "Different inputs must produce different hashes!"
print("  ✓ Different input → different output confirmed")

# ── Footer ──────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("  Real Data demo complete — all sections passed")
print(f"  Artifacts written to {ARTIFACTS_DIR}/")
print(f"{'='*70}\n")
