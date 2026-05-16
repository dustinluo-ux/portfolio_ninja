"""Bulk data update — pre-warm the local cache with OHLCV, news sentiment, and fundamentals."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
load_dotenv(project_root / ".env")

from portfolio_ninja.data_plane.real_adapter import RealDataAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Default universe ────────────────────────────────────────────────────────

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM",
    "JNJ", "V", "PG", "XOM", "UNH", "HD", "MA", "BAC", "PFE", "DIS", "CSCO",
]

# Default data directory matches real_adapter's _DEFAULT_BASE
DEFAULT_DATA_DIR = Path("C:/portfolio_ninja/trading_data/stock_market_data")
DEFAULT_SUBDIRS = ["nasdaq/csv", "forbes2000/csv", "nyse/csv"]

# Read API keys from environment
api_keys: dict[str, str] = {}
if key := os.environ.get("EODHD_API_KEY"):
    api_keys["eodhd"] = key
if key := os.environ.get("FMP_API_KEY"):
    api_keys["fmp"] = key


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk-download OHLCV data and refresh local cache.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Space-separated ticker list (default: bundled universe).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        required=False,
        help="Root directory for cached CSV files.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        default=False,
        help="Force full re-download of all data from scratch.",
    )
    parser.add_argument(
        "--freshness-days",
        type=int,
        default=1,
        help="Days since last data date before OHLCV is considered stale. (default: 1)",
    )
    parser.add_argument(
        "--news-freshness-days",
        type=int,
        default=7,
        help="Days since last data date before news is considered stale. (default: 7)",
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        default=False,
        help="Skip news sentiment download.",
    )
    parser.add_argument(
        "--skip-fundamentals",
        action="store_true",
        default=False,
        help="Skip fundamentals download.",
    )
    args = parser.parse_args()

    tickers = args.tickers if args.tickers is not None else DEFAULT_TICKERS
    data_dir = args.data_dir

    logger.info("bulk update — %d tickers, data dir=%s", len(tickers), data_dir)

    adapter = RealDataAdapter(
        base_path=data_dir,
        subdirs=DEFAULT_SUBDIRS,
        download_enabled=True,
        stale_ohlcv_days=args.freshness_days,
        stale_news_days=args.news_freshness_days,
        force_refresh=args.force_refresh,
        api_keys=api_keys,
    )

    ok = []
    failed = []
    skipped = []

    # Batch news update (once for all tickers)
    if not args.skip_news:
        if api_keys.get("eodhd"):
            logger.info("updating news sentiment (%d tickers)...", len(tickers))
            try:
                adapter._ensure_news(tickers, date.today(), window_days=365)
                logger.info("news sentiment updated")
            except Exception as e:
                logger.error("news sentiment update failed: %s", e)
        else:
            logger.info("EODHD_API_KEY not set — skipping news")

    for ticker in tickers:
        try:
            result = adapter._ensure_ohlcv(ticker, date.today())
            if result is not None:
                ok.append(ticker)
                logger.info("  [%d/%d] %s → %s", len(ok) + len(failed) + len(skipped), len(tickers), ticker, result)
            else:
                skipped.append(ticker)
                logger.warning("  [%d/%d] %s — no CSV found, download also failed", len(ok) + len(failed) + len(skipped), len(tickers), ticker)

            if not args.skip_fundamentals and api_keys.get("fmp"):
                try:
                    adapter._ensure_fundamentals(ticker)
                except Exception as e:
                    logger.warning("  fundamentals for %s failed: %s", ticker, e)
        except Exception as e:
            failed.append(ticker)
            logger.error("  [%d/%d] %s — ERROR: %s", len(ok) + len(failed) + len(skipped), len(tickers), ticker, e)

    logger.info("---")
    logger.info("done — ok=%d, skipped=%d, failed=%d", len(ok), len(skipped), len(failed))
    logger.info("data types: ohlcv=ok | news=%s | fundamentals=%s",
                "updated" if (not args.skip_news and api_keys.get("eodhd")) else "skipped",
                "updated" if (not args.skip_fundamentals and api_keys.get("fmp")) else "skipped")
    if ok:
        logger.info("  ok:      %s", ", ".join(ok))
    if skipped:
        logger.info("  skipped: %s", ", ".join(skipped))
    if failed:
        logger.info("  failed:  %s", ", ".join(failed))

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
