"""Production CLI entrypoint: run the full 11-module pipeline with real data.

Discovers tickers from the local CSV store, loads experiment config, runs
orchestrator.run(), and prints real artifacts for every pipeline stage.

Usage:
    conda run -n portfolio_ninja python scripts/run_pipeline.py
"""

from datetime import date, timedelta

from portfolio_ninja import orchestrator
from portfolio_ninja.data_plane.real_adapter import (
    _DEFAULT_BASE,
    CSV_SUBDIRS,
    RealDataAdapter,
    _find_csv_path,
    _load_csv_bars,
)
from portfolio_ninja.domain.stubs import StubExecutionAdapter
from portfolio_ninja.experiment_engine import load_experiment_config

_WINDOW_DAYS = 120
_MIN_BARS = 60
_MAX_TICKERS = 5


def _discover_tickers() -> list[str]:
    tickers: list[str] = []
    for subdir in CSV_SUBDIRS:
        d = _DEFAULT_BASE / subdir
        if not d.exists():
            continue
        for p in sorted(d.glob("*.csv")):
            t = p.stem.upper()
            if t in tickers:
                continue
            path = _find_csv_path(_DEFAULT_BASE, CSV_SUBDIRS, t)
            if path is None:
                continue
            try:
                _load_csv_bars(path, t, date.today(), _WINDOW_DAYS, min_rows=_MIN_BARS)
                tickers.append(t)
            except Exception:
                pass
        if len(tickers) >= _MAX_TICKERS:
            break
    return tickers[:_MAX_TICKERS]


def main() -> None:
    print("=" * 70)
    print("portfolio_ninja — full pipeline run")
    print(f"as_of_date : {date.today()}")
    print("=" * 70)

    if not _DEFAULT_BASE.exists():
        print(f"[ERROR] Trading data directory not found: {_DEFAULT_BASE}")
        print("        Run scripts/update_data.py first.")
        return

    tickers = _discover_tickers()
    if not tickers:
        print(f"[ERROR] No tickers with ≥{_MIN_BARS} bars in the {_WINDOW_DAYS}-day window.")
        return

    cfg = load_experiment_config()
    print()
    print("Experiment config (from config/experiment_config.yaml)")
    print(f"  scoring_model_id : {cfg['scoring_model_id']}")
    print(f"  top_n            : {cfg['top_n']}")
    print(f"  rebalance_freq   : {cfg['rebalance_freq']}")

    print()
    print(f"Tickers ({len(tickers)}): {tickers}")
    print()
    print("Running pipeline...")

    record = orchestrator.run(
        tickers=tickers,
        data_adapter=RealDataAdapter(download_enabled=False, base_path=_DEFAULT_BASE),
        exec_adapter=StubExecutionAdapter(),
        run_mode="backtest",
        window_days=_WINDOW_DAYS,
        scoring_model_id=cfg["scoring_model_id"],
        top_n=min(cfg["top_n"], len(tickers)),
        rebalance_freq=cfg["rebalance_freq"],
    )

    print()
    print("=" * 70)
    print("AuditRecord")
    print("=" * 70)
    print(f"  validation_status : {record.validation_status}")
    print(f"  tickers           : {record.tickers}")
    print()
    print("Pipeline hashes (64-char SHA-256):")
    for stage, h in record.pipeline_hashes.items():
        print(f"  {stage:<22} : {h[:16]}...")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
