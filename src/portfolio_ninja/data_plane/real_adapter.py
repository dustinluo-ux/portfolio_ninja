"""RealDataAdapter — load OHLCV data from local CSV files, sentiment from parquet, PE from FMP fundamentals.

Recycled from ai_supply_chain_trading/src/data/csv_provider.py.
Contamination fix CR-005: raises IncompleteDataError instead of print-not-raise.
_decimal_cast pattern from resilience_layer._cast_ohlc_to_decimal applied inline.
_csv_provider.load_prices() → _load_csv() ported to stdlib csv.DictReader (no pandas).
_csv_provider.find_csv_path() → _find_csv_path() ported directly.
_csv_provider.ensure_ohlcv() → ported as inline column normalization.
Sentiment loading: recycled from ai_supply_chain_trading/src/data/eodhd_news_loader.py (z-score pattern).
PE ratio: extracted from FMP fundamentals parquet (raw_json income statement).
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow.parquet as pq
import requests
import yfinance as yf

from portfolio_ninja.domain.exceptions import IncompleteDataError
from portfolio_ninja.domain.objects import (
    DataQualityReport,
    MarketDataset,
    OHLCVBar,
    TickerData,
    Universe,
)

logger = logging.getLogger(__name__)

# API endpoints
_YF_DOWNLOAD_DELAY = 1.0  # seconds between yfinance calls
_EODHD_NEWS_URL = "https://eodhd.com/api/news"
_EODHD_DELAY = 0.25
_FMP_INCOME_URL = "https://financialmodelingprep.com/api/v3/income-statement/"

CSV_SUBDIRS = ["nasdaq/csv", "forbes2000/csv", "nyse/csv"]
_DEFAULT_BASE = Path("C:/portfolio_ninja/trading_data/stock_market_data")

# Paths for sentiment and fundamentals — parallel to CSV data
_NEWS_DIR = Path("C:/portfolio_ninja/trading_data/news")
_FUNDAMENTALS_DIR = Path("C:/portfolio_ninja/trading_data/fundamentals")


def _parse_date(value: str) -> Optional[date]:
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _decimal(val: str) -> Decimal:
    """Cast CSV string to Decimal. Recycles _cast_ohlc_to_decimal idiom from legacy resilience_layer.py."""
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
    path: Path, ticker: str, as_of: date, window_days: int, min_rows: int = 60,
) -> list[OHLCVBar]:
    """Load OHLCV bars from a CSV file.

    RECYCLED from ai_supply_chain_trading/src/data/csv_provider.load_prices() + ensure_ohlcv().
    Uses stdlib csv.DictReader instead of pandas. Decimal cast per bar.
    """
    cutoff = as_of - timedelta(days=window_days)

    rows: list[dict] = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = {}
            for k, v in row.items():
                if not k or not k.strip():
                    # Unnamed columns (dates) go to "date" key
                    normalized["date"] = v.strip()
                else:
                    normalized[k.strip().lower()] = v.strip()
            rows.append(normalized)

    rows_by_date: dict[date, dict] = {}
    for row in rows:
        bar_date = _parse_date(row.get("date", ""))
        if bar_date is None:
            continue
        if bar_date < cutoff or bar_date > as_of:
            continue
        if bar_date not in rows_by_date:
            rows_by_date[bar_date] = row

    bars: list[OHLCVBar] = []
    for bar_date in sorted(rows_by_date):
        row = rows_by_date[bar_date]

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

        if close != close:  # close is NaN; skip this row entirely
            continue

        if open_p != open_p:  # NaN check
            open_p = close
        if high != high:
            high = close
        if low != low:
            low = close

        bars.append(OHLCVBar(date=bar_date, open=open_p, high=high, low=low, close=close, volume=volume))

    if len(bars) < min_rows:
        from portfolio_ninja.domain.exceptions import InsufficientDataError

        raise InsufficientDataError(f"{ticker}: only {len(bars)} bars loaded, minimum is {min_rows}")

    return bars


def _load_sentiment_for_ticker(ticker: str, news_dir: Path, as_of: date, window_days: int) -> Optional[Decimal]:
    """Load and average sentiment for a ticker from news parquets.

    RECYCLED from ai_supply_chain_trading/src/data/eodhd_news_loader.py z-score pattern.
    Reads all available parquet files in news_dir, filters to ticker and date window,
    returns mean sentiment. Parquet schema: Date, Ticker, Sentiment, Title, Source.
    """
    cutoff = as_of - timedelta(days=window_days)
    all_sentiments: list[float] = []

    for parquet_file in sorted(news_dir.glob("*.parquet")):
        try:
            table = pq.read_table(parquet_file)
            if table.num_rows == 0:
                continue
            df = table.to_pandas()
        except Exception:
            continue

        # Filter to our ticker and date window
        df_ticker = df[df["Ticker"].str.upper() == ticker.upper()]
        if df_ticker.empty:
            continue

        # Convert date strings to dates for filtering
        df_ticker = df_ticker.copy()
        df_ticker["parsed_date"] = pd.to_datetime(df_ticker["Date"]).dt.date

        mask = (df_ticker["parsed_date"] >= cutoff) & (df_ticker["parsed_date"] <= as_of)
        df_window = df_ticker.loc[mask]

        # Filter out NaN sentiment and collect values
        valid = df_window["Sentiment"].dropna()
        all_sentiments.extend(valid.astype(float).tolist())

    if not all_sentiments:
        return None

    return Decimal(str(round(sum(all_sentiments) / len(all_sentiments), 6)))


def _load_pe_ratio(ticker: str, fundamentals_dir: Path, latest_close: Decimal) -> Optional[Decimal]:
    """Extract PE ratio for a ticker from FMP fundamentals parquet."""
    fmp_path = fundamentals_dir / f"fmp_raw_{ticker.upper()}.parquet"
    if not fmp_path.exists():
        return None

    try:
        df = pq.read_table(fmp_path).to_pandas()
        income_stmt = df[df["statement"] == "income_statement"]
        if income_stmt.empty:
            return None

        raw_json = income_stmt.iloc[0]["raw_json"]
        reports = json.loads(raw_json)

        if not reports:
            return None

        latest_q = reports[0]
        eps_diluted = latest_q.get("epsDiluted", 0)
        if not eps_diluted or eps_diluted <= 0:
            return None

        pe = float(latest_close) / float(eps_diluted)
        return Decimal(str(round(pe, 4)))
    except Exception:
        return None


def _get_last_csv_date(csv_path: Path) -> Optional[date]:
    """Return the most recent date in an OHLCV CSV (index col 0). None if missing/unreadable."""
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        if df.empty:
            return None
        return pd.to_datetime(df.index.max()).date()
    except Exception:
        return None


def _get_last_parquet_date(parquet_path: Path, date_col: str = "Date") -> Optional[date]:
    """Return the most recent date in a parquet file's `date_col`. None if missing/unreadable."""
    if not parquet_path.exists():
        return None
    try:
        table = pq.read_table(parquet_path)
        if table.num_rows == 0:
            return None
        df = table.to_pandas()
        df[date_col] = pd.to_datetime(df[date_col]).dt.date
        return df[date_col].max()
    except Exception:
        return None


# ── Download functions (recycled from ai_supply_chain_trading) ──────────

def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0).astype(str).str.strip()
    return df


def _standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = _flatten_columns(df)
    if "Adj Close" in df.columns:
        df = df.rename(columns={"Adj Close": "Adjusted Close"})
    if "Adjusted Close" not in df.columns and "Close" in df.columns:
        df["Adjusted Close"] = df["Close"]
    canonical = ["Low", "Open", "Volume", "High", "Close", "Adjusted Close"]
    present = [c for c in canonical if c in df.columns]
    df = df[present]
    df.index.name = "Date"
    return df


def _download_ohlcv_yfinance(
    ticker: str, base_path: Path, start: str, end: str, subdirs: list[str], force_fresh: bool = False,
) -> Path:
    """Download OHLCV via yfinance, save to CSV with dedup merge.

    When force_fresh=True, skip merge and overwrite from scratch (used when CSV has unresolvable format issues).
    """
    from portfolio_ninja.data_plane.date_normalizer import normalize_csv

    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False, threads=False)
    if df is None or df.empty:
        raise ValueError(f"yfinance returned no data for {ticker}")

    df = _standardize_ohlcv(df)
    csv_path = base_path / subdirs[0] / f"{ticker.upper()}.csv"
    tmp_path = csv_path.with_suffix(".csv.tmp")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalize existing CSV before merge so mis-parsed dates are corrected first.
    # If normalization detects unresolvable format issues, trigger force-fresh re-download.
    if csv_path.exists() and not force_fresh:
        try:
            report = normalize_csv(csv_path)
            if report.needs_redownload:
                logger.warning(
                    "_download_ohlcv_yfinance: %s CSV has unresolvable format issues — force-fresh re-download",
                    ticker,
                )
                return _download_ohlcv_yfinance(ticker, base_path, start, end, subdirs, force_fresh=True)
        except Exception as exc:
            logger.warning("_download_ohlcv_yfinance: pre-merge normalize failed for %s: %s", ticker, exc)

    existing: pd.DataFrame | None = None
    if csv_path.exists() and not force_fresh:
        try:
            existing = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            existing.index = pd.to_datetime(existing.index, utc=True).tz_localize(None)
        except Exception:
            existing = None

    if existing is not None and not existing.empty:
        combined = pd.concat([existing, df])
        combined = combined[~combined.index.duplicated(keep="last")]
        df = combined.sort_index()

    df.to_csv(tmp_path)
    assert os.path.getsize(tmp_path) > 0, "OHLCV CSV empty"
    os.replace(tmp_path, csv_path)
    time.sleep(_YF_DOWNLOAD_DELAY)

    # Post-save normalize: sort, dedup, remove any future rows introduced by merge.
    try:
        normalize_csv(csv_path)
    except Exception as exc:
        logger.warning("_download_ohlcv_yfinance: post-save normalize failed for %s: %s", ticker, exc)

    return csv_path


def _download_news_sentiment_eodhd(
    tickers: list[str],
    news_dir: Path,
    api_key: str,
    from_date: str = "2020-01-01",
    to_date: str | None = None,
    force_fresh: bool = False,
) -> Path:
    """Download news sentiment via EODHD API, append to backfill parquet.

    When force_fresh=True, skip merge and overwrite from scratch (used for clean redownload).
    """
    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")

    out_file = news_dir / "eodhd_global_backfill.parquet"
    tmp_file = news_dir / "eodhd_global_backfill.parquet.tmp"

    all_rows: list[dict[str, str | float]] = []
    for ticker in tickers:
        offset = 0
        while True:
            time.sleep(_EODHD_DELAY)
            try:
                resp = requests.get(
                    _EODHD_NEWS_URL,
                    params={
                        "api_token": api_key, "s": ticker,
                        "from": from_date, "to": to_date,
                        "limit": 1000, "offset": offset, "fmt": "json",
                    },
                    timeout=120,
                )
            except requests.RequestException:
                break
            if resp.status_code != 200:
                break
            try:
                data = resp.json()
            except json.JSONDecodeError:
                break
            if not isinstance(data, list) or not data:
                break
            for item in data:
                if not isinstance(item, dict):
                    continue
                sent = item.get("sentiment")
                if not isinstance(sent, dict):
                    continue
                pol = sent.get("polarity")
                if pol is None:
                    continue
                try:
                    pol = float(pol)
                except (TypeError, ValueError):
                    continue
                raw_date = item.get("date") or item.get("datetime") or ""
                if isinstance(raw_date, str) and len(raw_date) >= 10:
                    all_rows.append({"Date": raw_date[:10], "Ticker": ticker.upper(), "Sentiment": pol})
            if len(data) < 1000:
                break
            offset += 1000

    if not all_rows:
        raise ValueError(f"No news sentiment data downloaded for tickers: {tickers}")

    df = pd.DataFrame(all_rows, columns=["Date", "Ticker", "Sentiment"])

    # Append to existing parquet if it exists (unless force_fresh=True)
    existing_file = news_dir / "eodhd_global_backfill.parquet"
    if existing_file.exists() and not force_fresh:
        try:
            existing_df = pq.read_table(existing_file).to_pandas()
            df = pd.concat([existing_df, df], ignore_index=True)
            df = df.drop_duplicates(subset=["Date", "Ticker"], keep="last")
            df = df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
        except Exception:
            pass  # keep newly downloaded data only if merge fails

    news_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(tmp_file, index=False, engine="pyarrow")
    assert os.path.getsize(tmp_file) > 0, "News parquet empty"
    os.replace(tmp_file, existing_file)
    return existing_file


def _download_fundamentals_fmp(
    ticker: str, fundamentals_dir: Path, api_key: str, force_fresh: bool = False,
) -> Path:
    """Download quarterly income statement via FMP API, save to parquet.

    When force_fresh=True, overwrite from scratch (used for clean redownload after data corruption).
    """
    out_path = fundamentals_dir / f"fmp_raw_{ticker.upper()}.parquet"
    tmp_path = fundamentals_dir / f"fmp_raw_{ticker.upper()}.parquet.tmp"

    url = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker.upper()}?period=quarter&apikey={api_key}"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise ValueError(f"FMP API returned {resp.status_code} for {ticker}")

    reports = resp.json()
    if not isinstance(reports, list) or not reports:
        raise ValueError(f"No income statement data for {ticker}")

    fundamentals_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{"statement": "income_statement", "raw_json": json.dumps(reports)}])
    df.to_parquet(tmp_path, index=False, engine="pyarrow")
    assert os.path.getsize(tmp_path) > 0, "FMP parquet empty"
    os.replace(tmp_path, out_path)
    time.sleep(0.25)
    return out_path


class RealDataAdapter:
    """Local-first data adapter: serve from indexed CSVs/parquets, download only when missing/stale.

    Recycled from ai_supply_chain_trading/src/data/csv_provider.py.
    Strategy: check local cache → if missing or stale, download to fill gap.
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        subdirs: Optional[list[str]] = None,
        news_dir: Optional[Path] = None,
        fundamentals_dir: Optional[Path] = None,
        download_enabled: bool = False,
        api_keys: Optional[dict[str, str]] = None,
        stale_ohlcv_days: int = 1,
        stale_news_days: int = 7,
        force_refresh: bool = False,
    ) -> None:
        self.base_path = base_path or _DEFAULT_BASE
        self.subdirs = list(subdirs) if subdirs is not None else list(CSV_SUBDIRS)
        self.news_dir = news_dir or _NEWS_DIR
        self.fundamentals_dir = fundamentals_dir or _FUNDAMENTALS_DIR
        self.download_enabled = download_enabled
        self.api_keys = api_keys or {}
        self.stale_ohlcv_days = stale_ohlcv_days
        self.stale_news_days = stale_news_days
        self.force_refresh = force_refresh

    def _ohlcv_stale(self, csv_path: Path) -> bool:
        """CSV is stale when the most recent data date is >= stale_ohlcv_days old."""
        last_date = _get_last_csv_date(csv_path)
        if last_date is None:
            return True
        return (date.today() - last_date).days >= self.stale_ohlcv_days

    def _news_stale(self) -> bool:
        """News is stale when the most recent data date in the backfill parquet is >= stale_news_days old."""
        pf = self.news_dir / "eodhd_global_backfill.parquet"
        last_date = _get_last_parquet_date(pf)
        if last_date is None:
            return True
        return (date.today() - last_date).days >= self.stale_news_days

    def _ensure_ohlcv(self, ticker: str, as_of: date) -> Path | None:
        """Find local CSV; if missing or stale, download incrementally to fill gap."""
        csv_path = _find_csv_path(self.base_path, self.subdirs, ticker)
        if csv_path is not None and not self._ohlcv_stale(csv_path) and not self.force_refresh:
            return csv_path

        if self.download_enabled:
            try:
                if self.force_refresh:
                    # Full re-download: start from scratch
                    start = "2015-01-01"
                elif csv_path is not None:
                    last_date = _get_last_csv_date(csv_path)
                    if last_date is not None:
                        start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    else:
                        start = "2015-01-01"
                else:
                    start = "2015-01-01"

                end = (as_of + timedelta(days=1)).strftime("%Y-%m-%d")
                return _download_ohlcv_yfinance(
                    ticker, self.base_path, start, end, self.subdirs,
                )
            except Exception as e:
                logger.warning("[real_adapter] %s: OHLCV download failed — %s", ticker, e)
        return csv_path

    def _ensure_news(self, tickers: list[str], as_of: date, window_days: int) -> bool:
        """If news exists and is fresh, skip download. Otherwise download incrementally if enabled."""
        if not self._news_stale() and not self.force_refresh:
            return True
        eodhd_key = self.api_keys.get("eodhd")
        if not self.download_enabled or not eodhd_key:
            return False
        pf = self.news_dir / "eodhd_global_backfill.parquet"
        last_date = _get_last_parquet_date(pf)
        if last_date is not None and not self.force_refresh:
            from_date = (last_date + timedelta(days=1)).isoformat()
        else:
            from_date = (as_of - timedelta(days=window_days)).isoformat()
        try:
            _download_news_sentiment_eodhd(
                tickers, self.news_dir, eodhd_key, from_date, as_of.isoformat(),
                force_fresh=self.force_refresh
            )
            return True
        except Exception as e:
            logger.warning("[real_adapter] news download failed — %s", e)
            return False

    def _ensure_fundamentals(self, ticker: str) -> Path | None:
        """Find local FMP parquet; skip if exists and not force_refresh, otherwise download if enabled."""
        fmp_path = self.fundamentals_dir / f"fmp_raw_{ticker.upper()}.parquet"
        if fmp_path.exists() and not self.force_refresh:
            return fmp_path
        fmp_key = self.api_keys.get("fmp")
        if self.download_enabled and fmp_key:
            try:
                return _download_fundamentals_fmp(ticker, self.fundamentals_dir, fmp_key, force_fresh=self.force_refresh)
            except Exception as e:
                logger.warning("[real_adapter] %s: fundamentals download failed — %s", ticker, e)
        return fmp_path if fmp_path.exists() else None

    def fetch(self, universe: Universe, window_days: int) -> MarketDataset:
        """Fetch data: local-first, download only when missing or stale."""
        data: dict[str, TickerData] = {}
        missing: list[str] = []
        warnings: list[str] = []

        # Pre-flight: check if any news download is needed
        need_news_download = self._news_stale() and self.download_enabled and self.api_keys.get("eodhd")
        if need_news_download:
            self._ensure_news(list(universe.tickers), universe.as_of_date, window_days)

        for ticker in universe.tickers:
            # ── OHLCV: local CSV first, download only if missing/stale ──
            csv_path = self._ensure_ohlcv(ticker, universe.as_of_date)
            if csv_path is None:
                logger.warning("[real_adapter] %s: no OHLCV data available", ticker)
                missing.append(ticker)
                continue

            try:
                bars = _load_csv_bars(csv_path, ticker, universe.as_of_date, window_days)
                if not bars:
                    missing.append(ticker)
                    continue

                latest_close = bars[-1].close

                # ── Sentiment: from local parquet (already refreshed if stale) ──
                sentiment = _load_sentiment_for_ticker(
                    ticker, self.news_dir, universe.as_of_date, window_days
                )
                if sentiment is None:
                    sentiment = Decimal("NaN")
                    warnings.append(f"{ticker}: no sentiment data")

                # ── PE ratio: local fundamentals, download if missing ──
                fmp_path = self._ensure_fundamentals(ticker)
                if fmp_path is not None:
                    pe = _load_pe_ratio(ticker, self.fundamentals_dir, latest_close)
                else:
                    pe = None
                if pe is None:
                    pe = Decimal("NaN")
                    warnings.append(f"{ticker}: no PE ratio available")

                data[ticker] = TickerData(
                    ohlcv=bars,
                    news_sentiment=sentiment,
                    pe_ratio=pe,
                )
            except Exception as e:
                logger.error("[real_adapter] %s: failed — %s", ticker, e)
                missing.append(ticker)

        source_tag = "api-real" if self.download_enabled else "csv-real"
        if missing:
            raise IncompleteDataError(missing_sources=missing, criticality="CRITICAL")

        quality = DataQualityReport()
        quality.warnings.extend(warnings)

        params_hash = hashlib.sha256(f"{universe.params_hash}|{source_tag}".encode()).hexdigest()

        return MarketDataset(
            data=data,
            source_data_version=source_tag,
            as_of_date=universe.as_of_date,
            params_hash=params_hash,
            validation_status="valid",
            reason_codes=[],
        )
