"""Generate a real MarketState sample from live CSV data."""
from datetime import date

from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.data_plane.real_adapter import (
    CSV_SUBDIRS,
    RealDataAdapter,
    _DEFAULT_BASE,
    _find_csv_path,
    _load_csv_bars,
)
from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.market_state_engine import compute_market_state
from portfolio_ninja.universe_gateway import create_universe

BASE = _DEFAULT_BASE
WINDOW_DAYS = 120
MIN_BARS = 60


def discover_tickers(n=20):
    tickers = []
    for subdir in CSV_SUBDIRS:
        csv_dir = BASE / subdir
        if not csv_dir.exists():
            continue
        for p in sorted(csv_dir.glob("*.csv")):
            t = p.stem.upper()
            if t not in tickers:
                tickers.append(t)
    return tickers[:n]


def has_bars(ticker):
    path = _find_csv_path(BASE, CSV_SUBDIRS, ticker)
    if path is None:
        return False
    try:
        _load_csv_bars(path, ticker, date.today(), WINDOW_DAYS, min_rows=MIN_BARS)
        return True
    except Exception:
        return False


candidates = discover_tickers(20)
good = [t for t in candidates if has_bars(t)][:5]
print(f"Tickers used:  {good}")
print(f"Window days:   {WINDOW_DAYS}")
print()

config = RunConfig(tickers=good[:3], run_mode="backtest", window_days=WINDOW_DAYS)
universe = create_universe(config)
adapter = RealDataAdapter(download_enabled=False, base_path=BASE)
ds = fetch_market_data(universe, adapter)
ms = compute_market_state(ds)

print(f"as_of_date:        {ms.as_of_date}")
print(f"regime:            {ms.regime}")
print(f"validation_status: {ms.validation_status}")
print(f"params_hash:       {ms.params_hash}")
print(f"reason_codes:      {ms.reason_codes}")
print()
print(f"{'Ticker':<10} {'momentum_20d':>14} {'volatility_20d':>15} {'rsi_14':>8} {'vol_ewma':>10} {'scsi':>10}")
print("-" * 72)
for ticker, tf in ms.features.items():
    print(
        f"{ticker:<10} {str(tf.momentum_20d):>14} {str(tf.volatility_20d):>15}"
        f" {str(tf.rsi_14):>8} {str(tf.volatility_ewma):>10} {str(tf.scsi):>10}"
    )

print()
print("Input bar counts:")
for ticker, td in ds.data.items():
    bars = td.ohlcv
    print(
        f"  {ticker}: {len(bars)} bars"
        f"  first={bars[0].date}  last={bars[-1].date}"
        f"  close[-1]={bars[-1].close}"
        f"  sentiment={td.news_sentiment}"
    )
