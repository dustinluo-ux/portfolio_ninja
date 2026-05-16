"""Find tickers with sufficient 2026 data in the 120-day window."""
from pathlib import Path

base = Path("C:/portfolio_ninja/trading_data/stock_market_data/nasdaq/csv")
good = []
for p in sorted(base.glob("*.csv")):
    try:
        with open(p) as f:
            lines = [
                l for l in f
                if l.strip()
                and not l.strip().startswith(",")
                and ",,,,," not in l
                and not l.startswith(",low")
            ]
        window_lines = [l for l in lines if l[:7] in ("2026-01", "2026-02", "2026-03", "2026-04", "2026-05")]
        if len(window_lines) >= 40:
            good.append((p.stem, len(window_lines)))
    except Exception:
        pass

print(f"Tickers with 40+ bars in 2026-01 to 2026-05 window: {len(good)}")
for ticker, count in good[:10]:
    print(f"  {ticker}: {count} bars")
