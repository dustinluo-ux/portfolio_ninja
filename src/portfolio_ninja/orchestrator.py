from portfolio_ninja.audit_monitor import assemble_audit_record
from portfolio_ninja.data_plane import fetch_market_data
from portfolio_ninja.domain.adapters import DataAdapter, ExecutionAdapter
from portfolio_ninja.domain.objects import AuditRecord, RunConfig
from portfolio_ninja.evaluation_engine import evaluate_cycle
from portfolio_ninja.execution_engine import execute_orders
from portfolio_ninja.experiment_engine import create_experiment_params
from portfolio_ninja.market_state_engine import compute_market_state
from portfolio_ninja.portfolio_construction_engine import construct_portfolio
from portfolio_ninja.risk_engine import evaluate_risk
from portfolio_ninja.score_arbitration_engine import rank_scores
from portfolio_ninja.scoring_engine import score_tickers
from portfolio_ninja.universe_gateway import create_universe


def run(
    tickers: list[str],
    data_adapter: DataAdapter,
    exec_adapter: ExecutionAdapter,
    run_mode: str = "backtest",
    window_days: int = 730,
    scoring_model_id: str = "stub_v1",
    top_n: int = 5,
    rebalance_freq: str = "daily",
) -> AuditRecord:
    config = RunConfig(tickers=tickers, run_mode=run_mode, window_days=window_days)

    universe = create_universe(config)
    market_dataset = fetch_market_data(universe, data_adapter)
    market_state = compute_market_state(market_dataset)
    experiment_params = create_experiment_params(
        config,
        scoring_model_id=scoring_model_id,
        top_n=top_n,
        rebalance_freq=rebalance_freq,
    )
    score_set = score_tickers(market_state, experiment_params)
    ranked_universe = rank_scores(score_set)
    target_portfolio = construct_portfolio(ranked_universe, experiment_params, market_state.regime)
    risk_decision = evaluate_risk(target_portfolio)
    execution_intent = execute_orders(risk_decision, exec_adapter, run_mode)
    evaluation_report = evaluate_cycle(execution_intent)

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

    return assemble_audit_record(
        evaluation_report=evaluation_report,
        pipeline_hashes=pipeline_hashes,
        run_mode=run_mode,
        tickers=universe.tickers,
    )
