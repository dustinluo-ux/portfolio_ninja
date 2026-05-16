"""One-shot script: show DataPlane input (Universe) and output (MarketDataset)."""
from datetime import date, timedelta

from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.data_plane.real_adapter import _DEFAULT_BASE, CSV_SUBDIRS, RealDataAdapter
from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.universe_gateway import create_universe

_WINDOW_DAYS = 120
_MIN_WINDOW_BARS = 60  # minimum real (non-empty) bars in the 120-day window
cutoff = date.today() - timedelta(days=_WINDOW_DAYS + 10)

tickers = []
for subdir in CSV_SUBDIRS:
    d = _DEFAULT_BASE / subdir
    if not d.exists():
        continue
    for p in sorted(d.glob("*.csv")):
        t = p.stem.upper()
        if t in tickers:
            continue
        try:
            with open(p) as f:
                lines = [
                    l.strip() for l in f
                    if l.strip()
                    and not l.strip().startswith(",")
                    and ",,,,," not in l
                ]
            # Count non-empty rows in the window
            window_bars = sum(
                1 for l in lines
                if l[:10] >= cutoff.isoformat() and not l.startswith(",")
            )
            if window_bars >= _MIN_WINDOW_BARS:
                tickers.append(t)
        except Exception:
            pass
    if len(tickers) >= 3:
        break
tickers = tickers[:3]

config = RunConfig(tickers=tickers, run_mode="backtest", window_days=_WINDOW_DAYS)
universe = create_universe(config)

print("=" * 62)
print("INPUT  (UniverseGateway -> DataPlane)")
print("=" * 62)
print(f"  tickers      : {universe.tickers}")
print(f"  run_mode     : {universe.run_mode}")
print(f"  window_days  : {universe.window_days}")
print(f"  as_of_date   : {universe.as_of_date}")
print(f"  params_hash  : {universe.params_hash[:16]}...")

adapter = RealDataAdapter(download_enabled=False, base_path=_DEFAULT_BASE)
dataset = fetch_market_data(universe, adapter)

print()
print("=" * 62)
print("OUTPUT (DataPlane -> MarketStateEngine)")
print("=" * 62)
print(f"  type               : MarketDataset")
print(f"  validation_status  : {dataset.validation_status}")
print(f"  as_of_date         : {dataset.as_of_date}")
print(f"  source_data_version: {dataset.source_data_version}")
print(f"  params_hash        : {dataset.params_hash[:16]}...")
print(f"  tickers covered    : {list(dataset.data.keys())}")

for ticker, td in dataset.data.items():
    first = td.ohlcv[0]
    last = td.ohlcv[-1]
    print()
    print(f"  [{ticker}]  bars={len(td.ohlcv)}")
    print(f"    first : {first.date}  O={first.open}  H={first.high}  L={first.low}  C={first.close}")
    print(f"    last  : {last.date}  O={last.open}  H={last.high}  L={last.low}  C={last.close}")
    print(f"    news_sentiment : {td.news_sentiment}")
    print(f"    pe_ratio       : {td.pe_ratio}")
