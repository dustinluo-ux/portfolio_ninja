"""Quick script: check date sort order in all 3 CSVs."""
import pandas as pd
from pathlib import Path

files = [
    Path("C:/portfolio_ninja/trading_data/stock_market_data/nasdaq/csv/NVDA.csv"),
    Path("C:/portfolio_ninja/trading_data/stock_market_data/nasdaq/csv/AAPL.csv"),
    Path("C:/portfolio_ninja/trading_data/stock_market_data/forbes2000/csv/MSFT.csv"),
]

for f in files:
    if not f.exists():
        print(f"{f.name}: NOT FOUND")
        continue
    df_raw = pd.read_csv(f)
    print(f"\n{f.name}: {len(df_raw)} rows")

    dates = pd.to_datetime(df_raw["Date"]).dt.strftime("%Y-%m-%d").tolist()
    first5 = dates[:5]
    last5 = dates[-5:]

    # Check if sorted ascending
    is_sorted = all(dates[i] <= dates[i+1] for i in range(len(dates)-1))
    print(f"  First 5: {first5}")
    print(f"  Last 5:  {last5}")
    print(f"  Sorted ascending: {is_sorted}")
