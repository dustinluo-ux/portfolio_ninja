# Project Map — portfolio_ninja

> Directory structure reference. Update when adding top-level directories.

---

## Root Layout

```
portfolio_ninja/
├── .claude/
│   ├── agents/           # Pipeline agents (8 total, HEAVY kit)
│   ├── rules/            # Modular rule files
│   └── settings.json     # ADR hook + ruff hook
├── .github/
│   └── workflows/
│       └── ci.yml        # CI: test + lint + secret check
├── docs/
│   ├── adr/              # Architectural decision records (MADR)
│   ├── contracts/        # Module contracts (11 total)
│   │   └── CONTRACT_INDEX.md
│   ├── checklists/       # COMPLETION_GATE.md, QUESTION_CLASSIFIER.md
│   ├── ARCHITECTURE.md   # Module map and execution graph (written by architect)
│   ├── CASE_FACTS.md     # Binding constraints — source of truth for all agents
│   └── escalation_protocol.md
├── scripts/
│   ├── auto_watcher.py   # HEAVY kit: watches CONTRACT_INDEX for build trigger
│   ├── check_adr.py      # ADR gate (wired to PreToolUse hook)
│   └── managed_builder.py  # Cloud builder (Anthropic Managed Agents)
├── src/
│   └── portfolio_ninja/  # Production code (populated by builder)
├── tests/                # Test files (populated by builder)
├── .env.example          # Env var template (never commit .env)
├── .gitignore
├── .mcp.json             # Filesystem MCP scoped to this project
├── ACTIVE_RISK_REGISTER.md
├── CLAUDE.md             # Project instructions
├── PROJECT_MAP.md        # This file
├── README.md             # Written after reviewer PASS
├── STATE_HANDOFF.md      # Session continuity
├── STORY.md              # Append-only audit trail
└── pyproject.toml
```

---

## Canonical Decision Path

```
Universe → MarketDataset → MarketState → ScoreSet → RankedUniverse
→ TargetPortfolio → RiskDecision → ExecutionIntent
→ EvaluationReport → AuditRecord
```

---

## Module → Source Path Mapping (post-build)

| Module | Source path | Contract |
|--------|-------------|---------|
| UniverseGateway | `src/portfolio_ninja/universe_gateway/` | `docs/contracts/universe_gateway.md` |
| DataPlane | `src/portfolio_ninja/data_plane/` | `docs/contracts/data_plane.md` |
| MarketStateEngine | `src/portfolio_ninja/market_state_engine/` | `docs/contracts/market_state_engine.md` |
| ScoringEngine | `src/portfolio_ninja/scoring_engine/` | `docs/contracts/scoring_engine.md` |
| ScoreArbitrationEngine | `src/portfolio_ninja/score_arbitration_engine/` | `docs/contracts/score_arbitration_engine.md` |
| PortfolioConstructionEngine | `src/portfolio_ninja/portfolio_construction_engine/` | `docs/contracts/portfolio_construction_engine.md` |
| RiskEngine | `src/portfolio_ninja/risk_engine/` | `docs/contracts/risk_engine.md` |
| ExecutionEngine | `src/portfolio_ninja/execution_engine/` | `docs/contracts/execution_engine.md` |
| EvaluationEngine | `src/portfolio_ninja/evaluation_engine/` | `docs/contracts/evaluation_engine.md` |
| ExperimentEngine | `src/portfolio_ninja/experiment_engine/` | `docs/contracts/experiment_engine.md` |
| AuditMonitor | `src/portfolio_ninja/audit_monitor/` | `docs/contracts/audit_monitor.md` |

---

## Directory Purposes

| Directory | Purpose |
|-----------|---------|
| `.claude/agents/` | All 8 pipeline agents; HEAVY kit |
| `.claude/rules/` | Architecture, testing, and Windows maintenance rules |
| `docs/adr/` | ADR records — required before `git commit` when `src/` has Python files |
| `docs/contracts/` | Sealed module contracts — the specification builders implement against |
| `scripts/` | Automation: ADR gate, managed builder, contract watcher |
| `src/` | Production code — populated by builder after contract approval |
| `tests/` | Tests — written alongside source by builder |
