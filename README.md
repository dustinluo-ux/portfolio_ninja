# portfolio_ninja

Automated stock-selection and portfolio-decision system — single-process, deterministic Python application with a sealed 11-module canonical pipeline.

portfolio_ninja accepts an externally supplied ticker universe and runs one canonical decision path (Universe → MarketDataset → MarketState → ScoreSet → RankedUniverse → TargetPortfolio → RiskDecision → ExecutionIntent → EvaluationReport → AuditRecord) identically in backtest, paper, and live modes. Only the data source adapter and execution adapter differ between modes.

## Why it exists

Portfolio research tools typically scatter logic across notebooks, scripts, and services, making reproducibility and auditing difficult. portfolio_ninja enforces a single deterministic path with full lineage on every output object so every cycle is reproducible, auditable, and mode-portable without changing domain logic.

## Quick start

```bash
conda create -n portfolio_ninja python=3.11
conda activate portfolio_ninja
pip install -e .

# Run smoke test (all dummy data, no external calls)
conda run -n portfolio_ninja python -m pytest tests/ -q

# Run one backtest cycle programmatically
conda run -n portfolio_ninja python - <<'EOF'
from portfolio_ninja.domain.stubs import StubDataAdapter, StubExecutionAdapter
from portfolio_ninja.orchestrator import run

audit = run(
    tickers=["AAPL", "MSFT", "GOOG", "AMZN", "TSLA"],
    data_adapter=StubDataAdapter(),
    exec_adapter=StubExecutionAdapter(),
    run_mode="backtest",
)
print(audit.cycle_id, audit.validation_status)
EOF
```

## Architecture

Eleven sealed modules execute sequentially in a single process. No services, no event buses, no async orchestration.

```
Universe → MarketDataset → MarketState → ScoreSet → RankedUniverse
→ TargetPortfolio → RiskDecision → ExecutionIntent
→ EvaluationReport → AuditRecord
```

ExperimentEngine is a side-input node: it supplies `ExperimentParams` to ScoringEngine and PortfolioConstructionEngine without sitting in the linear chain.

| Module | Purpose | Source path |
|--------|---------|------------|
| domain | Shared typed domain objects, adapter ABCs, stub implementations | `src/portfolio_ninja/domain/` |
| UniverseGateway | Validates ticker list + RunConfig; emits `Universe` | `src/portfolio_ninja/universe_gateway/` |
| DataPlane | Fetches OHLCV/news/fundamentals via adapter; emits `MarketDataset` | `src/portfolio_ninja/data_plane/` |
| MarketStateEngine | Computes momentum, volatility, RSI per ticker; emits `MarketState` | `src/portfolio_ninja/market_state_engine/` |
| ExperimentEngine | Constructs `ExperimentParams` (model, top_n, rebalance_freq) | `src/portfolio_ninja/experiment_engine/` |
| ScoringEngine | Scores tickers using model from `ExperimentParams`; emits `ScoreSet` | `src/portfolio_ninja/scoring_engine/` |
| ScoreArbitrationEngine | Ranks tickers; emits `RankedUniverse` | `src/portfolio_ninja/score_arbitration_engine/` |
| PortfolioConstructionEngine | Constructs target weights; emits `TargetPortfolio` | `src/portfolio_ninja/portfolio_construction_engine/` |
| RiskEngine | Validates weights (no-leverage, exposure limits); emits `RiskDecision` | `src/portfolio_ninja/risk_engine/` |
| ExecutionEngine | Translates risk-approved weights to orders via adapter; emits `ExecutionIntent` | `src/portfolio_ninja/execution_engine/` |
| EvaluationEngine | Computes cycle PnL/Sharpe/drawdown; emits `EvaluationReport` | `src/portfolio_ninja/evaluation_engine/` |
| AuditMonitor | Assembles full lineage from all upstream objects; emits `AuditRecord` (terminal) | `src/portfolio_ninja/audit_monitor/` |

All cross-module handoffs use typed domain objects (`src/portfolio_ninja/domain/objects.py`). No generic dicts. All monetary, price, and weight fields use `decimal.Decimal` — never `float`.

Adapter interfaces (`DataAdapter`, `ExecutionAdapter`) are ABCs in `src/portfolio_ninja/domain/adapters.py`. The MVP ships with `StubDataAdapter` (seeded RNG, seed=42) and `StubExecutionAdapter` (logs and returns). Swapping to a real broker or data feed requires only a new adapter class — no domain logic changes.

## Environment variables

| Name | Required | Description |
|------|----------|-------------|
| `ANTHROPIC_API_KEY` | No | Required only for `scripts/managed_builder.py` cloud builds |
| `BUDGET_USD` | No | If set, pipeline halts before breaching this USD ceiling |
| `MANAGED_BUILDER_ENVIRONMENT_ID` | No | Cloud builder environment ID (managed_builder.py) |
| `MANAGED_BUILDER_AGENT_ID` | No | Cloud builder agent ID (managed_builder.py) |
| `DATA_API_KEY` | No | Credential for real data adapter (future — not used in MVP) |
| `BROKER_API_KEY` | No | Credential for live execution adapter (future — not used in MVP) |
| `BROKER_API_SECRET` | No | Secret for live execution adapter (future — not used in MVP) |
| `RUN_MODE` | No | Default run mode: `backtest` (default) | `paper` | `live` |

Copy `.env.example` to `.env` and fill only what you need. Never commit `.env`.
