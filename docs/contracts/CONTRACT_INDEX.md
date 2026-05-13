# Contract Index — portfolio_ninja

| Module | Status | Upstream | Downstream | Contract |
|--------|--------|----------|------------|---------|
| domain_objects | implemented | — | all modules | [link](./domain_objects.md) |
| UniverseGateway | implemented | external (ticker list + RunConfig) | DataPlane | [link](./universe_gateway.md) |
| DataPlane | implemented | UniverseGateway, DataAdapter (injected) | MarketStateEngine | [link](./data_plane.md) |
| MarketStateEngine | implemented | DataPlane | ScoringEngine | [link](./market_state_engine.md) |
| ExperimentEngine | implemented | external (RunConfig) | ScoringEngine, PortfolioConstructionEngine (side-input) | [link](./experiment_engine.md) |
| ScoringEngine | implemented | MarketStateEngine, ExperimentEngine | ScoreArbitrationEngine | [link](./scoring_engine.md) |
| ScoreArbitrationEngine | implemented | ScoringEngine | PortfolioConstructionEngine | [link](./score_arbitration_engine.md) |
| PortfolioConstructionEngine | implemented | ScoreArbitrationEngine, ExperimentEngine | RiskEngine | [link](./portfolio_construction_engine.md) |
| RiskEngine | implemented | PortfolioConstructionEngine | ExecutionEngine | [link](./risk_engine.md) |
| ExecutionEngine | implemented | RiskEngine, ExecutionAdapter (injected) | EvaluationEngine | [link](./execution_engine.md) |
| EvaluationEngine | implemented | ExecutionEngine | AuditMonitor | [link](./evaluation_engine.md) |
| AuditMonitor | implemented | EvaluationEngine, Orchestrator (pipeline_hashes) | terminal (AuditRecord) | [link](./audit_monitor.md) |
