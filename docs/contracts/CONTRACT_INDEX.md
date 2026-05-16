# Contract Index — portfolio_ninja

| Module | Status | Version | Upstream | Downstream | Contract |
|--------|--------|---------|----------|------------|---------|
| domain_objects | implemented | v1 | — | all modules | [link](./domain_objects.md) |
| DateNormalizer | implemented | v1 | caller (real_adapter, normalize_csv CLI) | DataPlane (pre-merge gate), normalize_csv.py | [link](./date_normalizer.md) |
| UniverseGateway | implemented | v1 | external (ticker list + RunConfig) | DataPlane | [link](./universe_gateway.md) |
| DataPlane | implemented | v1 | UniverseGateway, DataAdapter (injected) | MarketStateEngine | [link](./data_plane.md) |
| MarketStateEngine | implemented | v1 | DataPlane | ScoringEngine | [link](./market_state_engine.md) |
| ExperimentEngine | implemented | v1 | external (RunConfig) | ScoringEngine, PortfolioConstructionEngine (side-input) | [link](./experiment_engine.md) |
| ScoringEngine | implemented | v1 | MarketStateEngine, ExperimentEngine | ScoreArbitrationEngine | [link](./scoring_engine.md) |
| ScoreArbitrationEngine | implemented | v1 | ScoringEngine | PortfolioConstructionEngine | [link](./score_arbitration_engine.md) |
| PortfolioConstructionEngine | implemented | v1 | ScoreArbitrationEngine, ExperimentEngine | RiskEngine | [link](./portfolio_construction_engine.md) |
| RiskEngine | implemented | v1 | PortfolioConstructionEngine | ExecutionEngine | [link](./risk_engine.md) |
| ExecutionEngine | implemented | v1 | RiskEngine, ExecutionAdapter (injected) | EvaluationEngine | [link](./execution_engine.md) |
| EvaluationEngine | implemented | v1 | ExecutionEngine | AuditMonitor | [link](./evaluation_engine.md) |
| AuditMonitor | implemented | v1 | EvaluationEngine, Orchestrator (pipeline_hashes) | terminal (AuditRecord) | [link](./audit_monitor.md) |
