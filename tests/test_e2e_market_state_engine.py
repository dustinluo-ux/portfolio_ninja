"""E2E proof: MarketStateEngine with real CSV data.

Verifies:
- compute_market_state() produces a valid MarketState from real OHLCV bars
- params_hash determinism and sensitivity
- All 5 Decimal features present and in range
- regime field present and valid
- Downstream ScoringEngine accepts MarketState without modification
- momentum sign matches actual price direction from real bars
Tests skip if the trading data directory is absent (CI without local data).
"""

from datetime import date
from decimal import Decimal

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
from portfolio_ninja.experiment_engine import create_experiment_params
from portfolio_ninja.market_state_engine import compute_market_state
from portfolio_ninja.scoring_engine import score_tickers
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


@pytest.fixture(scope="module")
def real_market_dataset(real_tickers):
    config = RunConfig(tickers=real_tickers[:3], run_mode="backtest", window_days=_WINDOW_DAYS)
    universe = create_universe(config)
    adapter = RealDataAdapter(download_enabled=False, base_path=_BASE)
    return fetch_market_data(universe, adapter)


@pytest.fixture(scope="module")
def real_market_state(real_market_dataset):
    return compute_market_state(real_market_dataset)


def test_e2e_market_state_engine_valid_state_from_real_bars(real_market_state, real_market_dataset):
    assert real_market_state.validation_status == "valid"
    assert real_market_state.as_of_date == real_market_dataset.as_of_date
    assert len(real_market_state.params_hash) == 64
    assert real_market_state.regime in ("EXPANSION", "CONTRACTION")


def test_e2e_market_state_engine_hash_is_deterministic(real_market_dataset):
    ms1 = compute_market_state(real_market_dataset)
    ms2 = compute_market_state(real_market_dataset)
    assert ms1.params_hash == ms2.params_hash


def test_e2e_market_state_engine_hash_changes_when_dataset_changes(real_tickers):
    config_a = RunConfig(tickers=real_tickers[:2], run_mode="backtest", window_days=_WINDOW_DAYS)
    config_b = RunConfig(tickers=real_tickers[:3], run_mode="backtest", window_days=_WINDOW_DAYS)
    adapter = RealDataAdapter(download_enabled=False, base_path=_BASE)
    ds_a = fetch_market_data(create_universe(config_a), adapter)
    ds_b = fetch_market_data(create_universe(config_b), adapter)
    assert compute_market_state(ds_a).params_hash != compute_market_state(ds_b).params_hash


def test_e2e_market_state_engine_all_features_are_decimal_and_in_range(real_market_state):
    for ticker, tf in real_market_state.features.items():
        assert isinstance(tf.momentum_20d, Decimal), f"{ticker}: momentum not Decimal"
        assert isinstance(tf.volatility_20d, Decimal), f"{ticker}: volatility not Decimal"
        assert isinstance(tf.rsi_14, Decimal), f"{ticker}: rsi not Decimal"
        assert isinstance(tf.volatility_ewma, Decimal), f"{ticker}: volatility_ewma not Decimal"
        assert isinstance(tf.scsi, Decimal), f"{ticker}: scsi not Decimal"
        assert Decimal("0") <= tf.rsi_14 <= Decimal("100"), f"{ticker}: rsi out of range"
        assert tf.volatility_ewma >= Decimal("0"), f"{ticker}: volatility_ewma < 0"


def test_e2e_market_state_engine_features_differentiate_across_tickers(real_market_state):
    tickers = list(real_market_state.features.keys())
    assert len(tickers) >= 2, "Need ≥2 tickers to compare"
    momenta = [real_market_state.features[t].momentum_20d for t in tickers]
    vols = [real_market_state.features[t].volatility_20d for t in tickers]
    assert len(set(momenta)) > 1 or len(set(vols)) > 1, (
        "All tickers have identical momentum and volatility — no differentiation"
    )


def test_e2e_market_state_engine_downstream_scoring_engine_accepts_output(
    real_market_state, real_tickers
):
    config = RunConfig(tickers=real_tickers[:3], run_mode="backtest", window_days=_WINDOW_DAYS)
    ep = create_experiment_params(config)
    ss = score_tickers(real_market_state, ep)
    assert ss.validation_status == "valid"
    assert set(ss.scores.keys()) == set(real_market_state.features.keys())


def test_e2e_market_state_engine_momentum_sign_matches_price_direction(
    real_market_state, real_market_dataset
):
    for ticker, tf in real_market_state.features.items():
        bars = real_market_dataset.data[ticker].ohlcv
        if len(bars) < 21:
            continue
        price_diff = bars[-1].close - bars[-21].close
        if price_diff == Decimal("0") or tf.momentum_20d == Decimal("0"):
            continue
        assert (price_diff > 0) == (tf.momentum_20d > 0), (
            f"{ticker}: price_diff={price_diff}, momentum={tf.momentum_20d} — signs disagree"
        )
