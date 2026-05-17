"""Production CLI entrypoint: run the full 11-module pipeline with real data.

Discovers tickers from the local CSV store, loads experiment config, runs
each pipeline step individually, and prints real artifacts for every stage.

Usage:
    conda run -n portfolio_ninja python scripts/run_pipeline.py
"""

from datetime import date

from portfolio_ninja.audit_monitor import assemble_audit_record
from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.data_plane.real_adapter import (
    _DEFAULT_BASE,
    CSV_SUBDIRS,
    RealDataAdapter,
    _find_csv_path,
    _load_csv_bars,
)
from portfolio_ninja.domain.objects import RunConfig
from portfolio_ninja.domain.stubs import StubExecutionAdapter
from portfolio_ninja.evaluation_engine import evaluate_cycle
from portfolio_ninja.execution_engine import execute_orders
from portfolio_ninja.experiment_engine import create_experiment_params, load_experiment_config
from portfolio_ninja.market_state_engine import compute_market_state
from portfolio_ninja.portfolio_construction_engine import construct_portfolio
from portfolio_ninja.risk_engine import evaluate_risk
from portfolio_ninja.score_arbitration_engine import rank_scores
from portfolio_ninja.scoring_engine import score_tickers
from portfolio_ninja.universe_gateway import create_universe

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
    scoring_model_id = cfg["scoring_model_id"]
    top_n = min(cfg["top_n"], len(tickers))
    rebalance_freq = cfg["rebalance_freq"]

    print()
    print("Experiment config (from config/experiment_config.yaml)")
    print(f"  scoring_model_id : {scoring_model_id}")
    print(f"  top_n            : {top_n}")
    print(f"  rebalance_freq   : {rebalance_freq}")
    print()
    print(f"Tickers ({len(tickers)}): {tickers}")
    print()
    print("Running pipeline steps...")

    data_adapter = RealDataAdapter(download_enabled=False, base_path=_DEFAULT_BASE)
    exec_adapter = StubExecutionAdapter()

    config = RunConfig(tickers=tickers, run_mode="backtest", window_days=_WINDOW_DAYS)

    universe = create_universe(config)
    print(f"  [1] universe         : {len(universe.tickers)} tickers, hash={universe.params_hash[:16]}...")

    market_dataset = fetch_market_data(universe, data_adapter)
    bar_counts = {t: len(td.ohlcv) for t, td in market_dataset.data.items()}
    print(f"  [2] market_dataset   : {len(bar_counts)} tickers, bars={bar_counts}, hash={market_dataset.params_hash[:16]}...")

    market_state = compute_market_state(market_dataset)
    print(f"  [3] market_state     : regime={market_state.regime}, hash={market_state.params_hash[:16]}...")
    print("       ticker features:")
    for ticker, feats in market_state.features.items():
        print(f"         {ticker:<8} momentum_20d={feats.momentum_20d:+.4f}  vol_20d={feats.volatility_20d:.4f}  rsi_14={feats.rsi_14:.2f}")

    experiment_params = create_experiment_params(
        config,
        scoring_model_id=scoring_model_id,
        top_n=top_n,
        rebalance_freq=rebalance_freq,
    )
    print(f"  [4] experiment_params: model={experiment_params.scoring_model_id}, hash={experiment_params.params_hash[:16]}...")

    score_set = score_tickers(market_state, experiment_params)
    print(f"  [5] score_set        : model={score_set.model_id}, {len(score_set.scores)} scores, hash={score_set.params_hash[:16]}...")
    print("       ticker scores (technical_composite_v1):")
    for ticker, score in sorted(score_set.scores.items(), key=lambda x: -x[1]):
        print(f"         {ticker:<8} score={score:.6f}")

    ranked_universe = rank_scores(score_set)
    print(f"  [6] ranked_universe  : {len(ranked_universe.ranked)} ranked, hash={ranked_universe.params_hash[:16]}...")
    print(f"       rank order: {[t for t, _ in ranked_universe.ranked]}")

    target_portfolio = construct_portfolio(ranked_universe, experiment_params, market_state.regime)
    print(f"  [7] target_portfolio : {len(target_portfolio.weights)} holdings, hash={target_portfolio.params_hash[:16]}...")
    print(f"       weights: { {t: str(w) for t, w in target_portfolio.weights.items()} }")

    risk_decision = evaluate_risk(target_portfolio)
    print(f"  [8] risk_decision    : approved={risk_decision.approved}, hash={risk_decision.params_hash[:16]}...")

    execution_intent = execute_orders(risk_decision, exec_adapter, "backtest")
    print(f"  [9] execution_intent : {len(execution_intent.orders)} orders, hash={execution_intent.params_hash[:16]}...")

    evaluation_report = evaluate_cycle(execution_intent)
    print(f"  [10] evaluation      : cycle_id={evaluation_report.cycle_id}, pnl={evaluation_report.pnl}")

    pipeline_hashes = {
        "universe": universe.params_hash,
        "market_dataset": market_dataset.params_hash,
        "market_state": market_state.params_hash,
        "experiment_params": experiment_params.params_hash,
        "score_set": score_set.params_hash,
        "ranked_universe": ranked_universe.params_hash,
        "target_portfolio": target_portfolio.params_hash,
        "risk_decision": risk_decision.params_hash,
        "execution_intent": execution_intent.params_hash,
    }

    record = assemble_audit_record(
        evaluation_report=evaluation_report,
        pipeline_hashes=pipeline_hashes,
        run_mode="backtest",
        tickers=universe.tickers,
    )

    print()
    print("=" * 70)
    print("AuditRecord")
    print("=" * 70)
    print(f"  validation_status : {record.validation_status}")
    print(f"  cycle_id          : {record.cycle_id}")
    print(f"  tickers           : {record.tickers}")
    print(f"  completed_at      : {record.completed_at.isoformat()}")
    print()
    print("Pipeline hashes (64-char SHA-256):")
    for stage, h in record.pipeline_hashes.items():
        print(f"  {stage:<22} : {h[:16]}...")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
