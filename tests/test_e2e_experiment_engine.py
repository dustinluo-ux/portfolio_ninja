"""E2E tests for ExperimentEngine config-driven parameters.

No mocks — uses real config/experiment_config.yaml and real CSV data.
Tests are skipped if the trading data directory does not exist.
"""

from datetime import date

import pytest

from portfolio_ninja import orchestrator
from portfolio_ninja.data_plane.real_adapter import (
    _DEFAULT_BASE,
    CSV_SUBDIRS,
    RealDataAdapter,
    _find_csv_path,
    _load_csv_bars,
)
from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.domain.stubs import StubExecutionAdapter
from portfolio_ninja.experiment_engine import create_experiment_params, load_experiment_config
from portfolio_ninja.experiment_engine.config_loader import _DEFAULT_CONFIG_PATH

_BASE = _DEFAULT_BASE
_WINDOW_DAYS = 120
_MIN_BARS_ADAPTER = 60


def _discover_tickers(n: int = 20) -> list[str]:
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
    candidates = _discover_tickers(n=20)
    good = [t for t in candidates if _has_sufficient_bars(t)]
    if not good:
        pytest.skip(f"No tickers with ≥{_MIN_BARS_ADAPTER} in-window bars found")
    return good[:3]


def test_e2e_experiment_engine_config_file_exists_and_is_valid():
    assert _DEFAULT_CONFIG_PATH.exists(), f"Config file missing: {_DEFAULT_CONFIG_PATH}"
    cfg = load_experiment_config()
    assert cfg["scoring_model_id"] == "technical_composite_v1"
    assert cfg["top_n"] == 5
    assert cfg["rebalance_freq"] == "daily"


def test_e2e_experiment_engine_default_model_is_technical_composite_v1():
    cfg = load_experiment_config()
    config = RunConfig(tickers=["AAPL"], run_mode="backtest", window_days=_WINDOW_DAYS)
    ep = create_experiment_params(
        config,
        scoring_model_id=cfg["scoring_model_id"],
        top_n=cfg["top_n"],
        rebalance_freq=cfg["rebalance_freq"],
    )
    assert ep.scoring_model_id == "technical_composite_v1"
    assert ep.validation_status == "valid"


def test_e2e_experiment_engine_params_flow_through_pipeline(real_tickers):
    record = orchestrator.run(
        tickers=real_tickers,
        data_adapter=RealDataAdapter(download_enabled=False, base_path=_BASE),
        exec_adapter=StubExecutionAdapter(),
        run_mode="backtest",
        window_days=_WINDOW_DAYS,
    )
    assert record.validation_status == "valid"
    assert "experiment_params" in record.pipeline_hashes
    assert len(record.pipeline_hashes["experiment_params"]) == 64


def test_e2e_experiment_engine_output_changes_when_model_changes(real_tickers):
    record_a = orchestrator.run(
        tickers=real_tickers,
        data_adapter=RealDataAdapter(download_enabled=False, base_path=_BASE),
        exec_adapter=StubExecutionAdapter(),
        run_mode="backtest",
        window_days=_WINDOW_DAYS,
        scoring_model_id="technical_composite_v1",
    )
    record_b = orchestrator.run(
        tickers=real_tickers,
        data_adapter=RealDataAdapter(download_enabled=False, base_path=_BASE),
        exec_adapter=StubExecutionAdapter(),
        run_mode="backtest",
        window_days=_WINDOW_DAYS,
        scoring_model_id="stub_v1",
    )
    assert (
        record_a.pipeline_hashes["experiment_params"]
        != record_b.pipeline_hashes["experiment_params"]
    )
