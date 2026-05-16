import yfinance as yf
from datetime import date, timedelta

df = yf.download("NVDA", start="2026-05-01", end=(date.today() + timedelta(days=1)).strftime("%Y-%m-%d"), progress=False, auto_adjust=False)
print(type(df))
if df is not None and not len(df) == 0:
    print(df.tail(5))
    print(f"Rows: {len(df)}, Date range: {df.index[0]} to {df.index[-1]}")
else:
    print("No data returned")
