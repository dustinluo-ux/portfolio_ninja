import hashlib
import json
from datetime import date

from portfolio_ninja.domain.objects import RunConfig, Universe


def create_universe(config: RunConfig, as_of_date: date | None = None) -> Universe:
    if not config.tickers:
        raise ValueError("tickers must not be empty")

    valid_modes = {"backtest", "paper", "live"}
    if config.run_mode not in valid_modes:
        raise ValueError(f"run_mode '{config.run_mode}' not in {valid_modes}")

    if config.window_days <= 0:
        raise ValueError("window_days must be > 0")

    reason_codes: list[str] = []
    unique_tickers = sorted(set(config.tickers))
    if len(unique_tickers) < len(config.tickers):
        reason_codes.append("tickers_deduplicated")

    aod = as_of_date if as_of_date is not None else date.today()

    hash_input = json.dumps(
        {"tickers": unique_tickers, "run_mode": config.run_mode, "window_days": config.window_days},
        sort_keys=True,
    ).encode()
    params_hash = hashlib.sha256(hash_input).hexdigest()

    regime_tickers = ["SPY"]

    return Universe(
        tickers=unique_tickers,
        run_mode=config.run_mode,
        window_days=config.window_days,
        as_of_date=aod,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=reason_codes,
        regime_tickers=regime_tickers,
    )
