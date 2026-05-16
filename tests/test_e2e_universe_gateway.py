"""E2E proof: UniverseGateway with real tickers discovered from local CSV files.

Verifies:
- create_universe() produces a valid Universe from real ticker lists
- params_hash changes when inputs change (determinism + sensitivity)
- Universe output is accepted by DataPlane without adapter hacks
- No dummy/static ticker lists — all tickers sourced from local CSV store
Tests skip if the trading data directory is absent (CI without local data).
"""

from datetime import date

import pytest

from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.data_plane.real_adapter import (
    _DEFAULT_BASE,
    CSV_SUBDIRS,
    RealDataAdapter,
    _find_csv_path,
    _load_csv_bars,
)
from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.universe_gateway import create_universe

_BASE = _DEFAULT_BASE
_WINDOW_DAYS = 120
_MIN_BARS_ADAPTER = 60


def _discover_tickers(n: int = 30) -> list[str]:
    tickers: list[str] = []
    for subdir in CSV_SUBDIRS:
        csv_dir = _BASE / subdir
        if not csv_dir.exists():
            continue
        for csv_path in sorted(csv_dir.glob("*.csv")):
            ticker = csv_path.stem.upper()
            if ticker not in tickers:
                tickers.append(ticker)
    return tickers[:n]


def _has_sufficient_bars(ticker: str) -> bool:
    path = _find_csv_path(_BASE, CSV_SUBDIRS, ticker)
    if path is None or not path.exists():
        return False
    try:
        _load_csv_bars(path, ticker, date.today(), _WINDOW_DAYS, min_rows=_MIN_BARS_ADAPTER)
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def real_tickers():
    if not _BASE.exists():
        pytest.skip(f"Trading data directory not found: {_BASE}")
    candidates = _discover_tickers(n=30)
    good = [t for t in candidates if _has_sufficient_bars(t)]
    if len(good) < 2:
        pytest.skip(f"Need ≥2 tickers with sufficient in-window bars; found {len(good)}")
    return good[:5]


def test_e2e_universe_gateway_valid_universe_from_real_tickers(real_tickers):
    """Universe produced from real CSV-discovered tickers is valid."""
    config = RunConfig(tickers=real_tickers, run_mode="backtest", window_days=_WINDOW_DAYS)
    universe = create_universe(config)

    assert universe.validation_status == "valid"
    assert set(universe.tickers) == set(real_tickers)
    assert universe.tickers == sorted(set(real_tickers))
    assert universe.run_mode == "backtest"
    assert universe.window_days == _WINDOW_DAYS
    assert len(universe.params_hash) == 64
    assert universe.as_of_date == date.today()
    assert universe.reason_codes == []
    assert "SPY" in universe.regime_tickers


def test_e2e_universe_gateway_hash_is_deterministic(real_tickers):
    """Identical inputs always produce the same params_hash."""
    config = RunConfig(tickers=real_tickers, run_mode="backtest", window_days=_WINDOW_DAYS)
    u1 = create_universe(config, as_of_date=date(2026, 1, 15))
    u2 = create_universe(config, as_of_date=date(2026, 1, 15))
    assert u1.params_hash == u2.params_hash


def test_e2e_universe_gateway_hash_changes_with_ticker_change(real_tickers):
    """Adding a ticker produces a different params_hash (sensitivity check)."""
    config_a = RunConfig(tickers=real_tickers[:2], run_mode="backtest", window_days=_WINDOW_DAYS)
    config_b = RunConfig(tickers=real_tickers[:3], run_mode="backtest", window_days=_WINDOW_DAYS)
    aod = date(2026, 1, 15)
    assert create_universe(config_a, as_of_date=aod).params_hash != create_universe(config_b, as_of_date=aod).params_hash


def test_e2e_universe_gateway_hash_changes_with_run_mode(real_tickers):
    """Changing run_mode produces a different params_hash."""
    aod = date(2026, 1, 15)
    u_bt = create_universe(RunConfig(tickers=real_tickers, run_mode="backtest", window_days=_WINDOW_DAYS), as_of_date=aod)
    u_paper = create_universe(RunConfig(tickers=real_tickers, run_mode="paper", window_days=_WINDOW_DAYS), as_of_date=aod)
    assert u_bt.params_hash != u_paper.params_hash


def test_e2e_universe_gateway_hash_changes_with_window(real_tickers):
    """Changing window_days produces a different params_hash."""
    aod = date(2026, 1, 15)
    u_120 = create_universe(RunConfig(tickers=real_tickers, run_mode="backtest", window_days=120), as_of_date=aod)
    u_365 = create_universe(RunConfig(tickers=real_tickers, run_mode="backtest", window_days=365), as_of_date=aod)
    assert u_120.params_hash != u_365.params_hash


def test_e2e_universe_gateway_downstream_dataplane_accepts_output(real_tickers):
    """DataPlane (downstream consumer) accepts Universe without modification."""
    config = RunConfig(tickers=real_tickers, run_mode="backtest", window_days=_WINDOW_DAYS)
    universe = create_universe(config)
    adapter = RealDataAdapter(download_enabled=False, base_path=_BASE)
    dataset = fetch_market_data(universe, adapter)

    assert dataset.validation_status == "valid"
    assert set(dataset.data.keys()) == set(universe.tickers)
    assert len(dataset.params_hash) == 64


def test_e2e_universe_gateway_dedup_with_real_tickers(real_tickers):
    """Duplicate real tickers are deduplicated and reason_codes reflect it."""
    duplicated = real_tickers + [real_tickers[0]]
    config = RunConfig(tickers=duplicated, run_mode="backtest", window_days=_WINDOW_DAYS)
    universe = create_universe(config)

    assert "tickers_deduplicated" in universe.reason_codes
    assert universe.tickers == sorted(set(real_tickers))
    assert universe.validation_status == "valid"
