"""RealDataAdapter — load OHLCV data from local CSV files.

Recycled from ai_supply_chain_trading/src/data/csv_provider.py.
Contamination fix CR-005: raises IncompleteDataError instead of print-not-raise.
_decimal_cast pattern from resilience_layer._cast_ohlc_to_decimal applied inline.
_csv_provider.load_prices() → _load_csv() ported to stdlib csv.DictReader (no pandas).
_csv_provider.find_csv_path() → _find_csv_path() ported directly.
_csv_provider.ensure_ohlcv() → ported as inline column normalization.
"""

from __future__ import annotations

import csv
import hashlib
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

from portfolio_ninja.domain.exceptions import IncompleteDataError
from portfolio_ninja.domain.objects import (
    DataQualityReport,
    MarketDataset,
    OHLCVBar,
    TickerData,
    Universe,
)

logger = logging.getLogger(__name__)

# Subdirectory search order — ported from legacy ARCHITECTURE.md / csv_provider.py
CSV_SUBDIRS = ["nasdaq/csv", "forbes2000/csv", "nyse/csv"]

# Default path (overridable via constructor or TRADING_DATA_DIR env var)
_DEFAULT_BASE = Path("C:/portfolio_ninja/trading_data/stock_market_data")


def _parse_date(value: str) -> Optional[date]:
    """Parse date from CSV row. Tries YYYY-MM-DD first, then common fallbacks."""
    if not value or not value.strip():
        return None
    value = value.strip()
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _decimal(val: str) -> Decimal:
    """Cast CSV string to Decimal. Recycles _cast_ohlc_to_decimal(idiom from legacy resilience_layer.py."""
    cleaned = val.strip().replace(",", "")
    if not cleaned or cleaned.lower() in ("nan", "none", ""):
        return Decimal("NaN")
    try:
        return Decimal(str(float(cleaned)))
    except (ValueError, TypeError):
        return Decimal("NaN")


def _find_csv_path(base_dir: Path, subdirs: list[str], ticker: str) -> Optional[Path]:
    """Search subdirectories for {TICKER}.csv case-insensitive.

    RECYCLED from ai_supply_chain_trading/src/data/csv_provider.find_csv_path().
    Simplified: no duplicate-ticker resolution (we take first match in search order).
    """
    ticker_clean = ticker.upper().replace(".CSV", "")
    for subdir in subdirs:
        search_dir = base_dir / subdir
        if not search_dir.is_dir():
            continue
        for path in search_dir.iterdir():
            if path.is_file() and path.stem.upper() == ticker_clean:
                return path
    return None


def _load_csv_bars(
    path: Path,
    ticker: str,
    as_of: date,
    window_days: int,
    min_rows: int = 60,
) -> list[OHLCVBar]:
    """Load OHLCV bars from a CSV file.

    RECYCLED from ai_supply_chain_trading/src/data/csv_provider.load_prices() + ensure_ohlcv().
    Uses stdlib csv.DictReader instead of pandas.
    Applies Decimal(str(float(val))) cast per bar (from legacy _cast_ohlc_to_decimal).
    """
    cutoff = as_of - timedelta(days=window_days)

    # Read all rows into memory first so we can sort by date
    rows: list[dict] = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize column names to lowercase, stripped
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            rows.append(row)

    rows_by_date: dict[date, dict] = {}
    for row in rows:
        bar_date = _parse_date(row.get("date", ""))
        if bar_date is None:
            continue
        if bar_date < cutoff or bar_date > as_of:
            continue
        # Latest date wins if duplicates
        if bar_date not in rows_by_date:
            rows_by_date[bar_date] = row

    # Build OHLCV bars (sorted chronologically)
    bars: list[OHLCVBar] = []
    for bar_date in sorted(rows_by_date):
        row = rows_by_date[bar_date]
        # Column mapping: handle duplicates (csv_provider has Low,Open,Volume,High,Close duplicates)
        def _col(primary: str, fallback: str) -> Decimal:
            if primary in row and row[primary]:
                return _decimal(row[primary])
            if fallback in row and row[fallback]:
                return _decimal(row[fallback])
            return Decimal("NaN")

        high = _col("high", "High")
        low = _col("low", "Low")
        open_p = _col("open", "Open")
        close = _col("close", "Close")
        volume_str = row.get("volume", row.get("Volume", ""))
        volume = int(float(volume_str.strip())) if volume_str.strip() else 0

        # ensure_ohlcv pattern: fall back to close for missing OHLC
        if open_p != open_p:  # NaN check
            open_p = close
        if high != high:
            high = close
        if low != low:
            low = close

        bars.append(OHLCVBar(
            date=bar_date,
            open=open_p,
            high=high,
            low=low,
            close=close,
            volume=volume,
        ))

    if len(bars) < min_rows:
        from portfolio_ninja.domain.exceptions import InsufficientDataError
        raise InsufficientDataError(
            f"{ticker}: only {len(bars)} bars loaded, minimum is {min_rows}"
        )

    return bars


class RealDataAdapter:
    """Load OHLCV data from local CSV files.

    Recycled from ai_supply_chain_trading/src/data/csv_provider.py.
    Contamination fixes applied:
    - CR-005: raises IncompleteDataError instead of print-not-raise
    - CR-003: all OHLCV fields are Decimal, never float
    - No pandas dependency — uses stdlib csv.DictReader
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        subdirs: Optional[list[str]] = None,
    ) -> None:
        self.base_path = base_path or _DEFAULT_BASE
        self.subdirs = list(subdirs) if subdirs is not None else list(CSV_SUBDIRS)

    def fetch(self, universe: Universe, window_days: int) -> MarketDataset:
        """Fetch OHLCV data for all tickers in universe via local CSV files."""
        data: dict[str, TickerData] = {}
        missing: list[str] = []

        for ticker in universe.tickers:
            csv_path = _find_csv_path(self.base_path, self.subdirs, ticker)
            if csv_path is None:
                logger.warning(
                    "[real_adapter] %s: no CSV found in %s (subdirs: %s)",
                    ticker,
                    self.base_path,
                    self.subdirs,
                )
                missing.append(ticker)
                continue
            try:
                bars = _load_csv_bars(csv_path, ticker, universe.as_of_date, window_days)
                if not bars:
                    logger.warning(
                        "[real_adapter] %s: no bars in window [%s..%s]",
                        ticker,
                        universe.as_of_date - timedelta(days=window_days),
                        universe.as_of_date,
                    )
                    missing.append(ticker)
                    continue

                # Decimal cast idiom from resilience_layer._cast_ohlc_to_decimal
                # already applied in _load_csv_bars via Decimal(str(float(val)))
                ticker_data = TickerData(
                    ohlcv=bars,
                    news_sentiment=Decimal("0"),  # stub — no news integration yet
                    pe_ratio=Decimal("0"),  # stub — no fundamentals integration yet
                )
                data[ticker] = ticker_data
            except Exception as e:
                logger.error(
                    "[real_adapter] %s: failed to load %s — %s",
                    ticker,
                    csv_path,
                    e,
                )
                missing.append(ticker)

        if missing:
            raise IncompleteDataError(
                missing_sources=missing,
                criticality="CRITICAL",
            )

        quality = DataQualityReport()
        quality.warnings.append("news_sentiment and pe_ratio are stubs (no fundamentals integration)")

        params_hash = hashlib.sha256(
            f"{universe.params_hash}|csv-real".encode()
        ).hexdigest()

        return MarketDataset(
            data=data,
            source_data_version="csv-real",
            as_of_date=universe.as_of_date,
            params_hash=params_hash,
            validation_status="valid",
            reason_codes=[],
        )
