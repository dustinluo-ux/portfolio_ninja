# Plan: portfolio_ninja MVP — Architecture Hardening Pass

## Context

MVP is complete, verified, and committed. All 11 modules are wired, 97.05% coverage, e2e demo passes.
This pass hardens the spine before legacy mining begins. No real data providers, ML models, broker integrations, or legacy code. Only the 10 hardening items listed by the user.

---

## Deliverables

| Artifact | Path | Status |
|----------|------|--------|
| Updated domain objects | `src/portfolio_ninja/domain/objects.py` | to modify |
| Updated adapter interface | `src/portfolio_ninja/domain/adapters.py` | to modify |
| Updated stubs | `src/portfolio_ninja/domain/stubs.py` | to modify |
| Updated execution_engine | `src/portfolio_ninja/execution_engine/execution_engine.py` | to modify |
| Updated evaluation_engine | `src/portfolio_ninja/evaluation_engine/evaluation_engine.py` | to modify |
| Updated audit_monitor | `src/portfolio_ninja/audit_monitor/audit_monitor.py` | to modify |
| Updated orchestrator | `src/portfolio_ninja/orchestrator.py` | to modify |
| Updated operator_report | `src/portfolio_ninja/operator_report.py` | to modify |
| Updated contracts (all 12) | `docs/contracts/*.md` | to modify |
| Updated ARCHITECTURE.md | `docs/ARCHITECTURE.md` | to modify |
| ADR for execution lifecycle | `docs/adr/0002-execution-lifecycle-and-fill-model.md` | to create |
| New hardening tests | `tests/test_hardening.py` | to create |
| Updated existing tests | `tests/test_domain.py`, `tests/test_execution_engine.py`, `tests/test_evaluation_engine.py`, `tests/test_audit_monitor.py`, `tests/test_smoke.py` | to modify |
| Hardening summary | `HARDENING_SUMMARY.md` | to create |

---

## Change Set (10 Items)

### Item 1 — Execution Lifecycle Separation

**Current problem:** ExecutionEngine computes orders AND calls adapter.submit() but emits only `ExecutionIntent`. EvaluationEngine takes `ExecutionIntent` directly — meaning it consumes a pre-submission object as if it had execution data. FillReport doesn't exist.

**New domain objects** (added to `domain/objects.py`):

```python
@dataclass
class Fill:
    ticker: str
    direction: str       # "buy" | "sell"
    quantity: Decimal    # quantity filled (stub: = order.quantity)
    price: Decimal       # fill price (stub: Decimal("0"))

@dataclass
class FillReport:
    fills: list[Fill]
    cycle_id: str
    as_of_date: date
    params_hash: str
    is_stub: bool = True
    stub_reason: str = "FillReport is a placeholder; real fills require broker callbacks or reconciliation"
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)
    # validate(): cycle_id non-empty, params_hash non-empty, status valid

@dataclass
class ExecutionResult:
    execution_intent: ExecutionIntent  # the intent that was submitted
    success: bool
    adapter_id: str
    adapter_ref_ids: dict[str, str]    # ticker → broker ref (stub: empty)
    submitted_at: datetime
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)
    # validate(): adapter_id non-empty, params_hash non-empty, status valid
```

**Pipeline changes:**
- `ExecutionAdapter.submit(intent) -> None` changes to `-> ExecutionResult`
- `StubExecutionAdapter.submit()` constructs and returns a stub `ExecutionResult` (success=True, adapter_ref_ids={}, submitted_at=now())
- `execution_engine.execute_orders()` returns `ExecutionResult` (not `ExecutionIntent`)
  - Still computes `ExecutionIntent` internally; passes it to adapter.submit()
  - Returns adapter's `ExecutionResult`
- `evaluation_engine.evaluate_cycle(execution_result: ExecutionResult)` — takes `ExecutionResult`
  - Creates stub `FillReport` from `execution_result.execution_intent.orders`
  - Returns `EvaluationReport` with `is_stub=True`
- Orchestrator: stores both `execution_intent.params_hash` and `execution_result.params_hash` in pipeline_hashes (10 keys total, up from 9)

**ADR required:** `docs/adr/0002-execution-lifecycle-and-fill-model.md` — records decision to separate intent/result/fill as three objects, adapter interface change from `-> None` to `-> ExecutionResult`.

---

### Item 2 — Contract Versioning

Add to **every** contract (all 12, before `## Purpose`):

```markdown
## Version
v1 (frozen 2026-05-13). Changes to inputs, outputs, or invariants require an Architecture Decision Record in `docs/adr/`. Cross-node contract changes are forbidden without an explicit version bump and ADR approval.
```

Update `CONTRACT_INDEX.md` to add a `Version` column showing `v1` for all rows.

---

### Item 3 — Orchestrator Ownership

**Verification:** Grep that no pipeline module imports from another pipeline module's source path (only `domain` imports are permitted between modules).

**ARCHITECTURE.md additions** — new section `## Orchestrator Invariants`:
- Only `src/portfolio_ninja/orchestrator.py` may call pipeline module functions
- No module may import from another pipeline module's source path (only `domain` imports permitted)
- No module may self-trigger, schedule tasks, call downstream modules, fetch hidden dependencies, or mutate global state
- Modules are pure functions: typed input → typed output, no side effects outside their injected adapter

---

### Item 4 — State Boundary Definition

**ARCHITECTURE.md additions** — new section `## State Boundaries`:

| Category | Definition | Examples |
|----------|-----------|---------|
| Ephemeral runtime state | Created and consumed within one `run()` call; never persisted | All 10 pipeline handoff objects, FillReport |
| Persisted audit state | Intended for future persistence; currently in-memory only | `AuditRecord` |
| Reproducible input state | Given same `RunConfig` + same adapter (e.g., seeded stub), output is deterministic | `RunConfig`, `StubDataAdapter(seed=42)` |
| Forbidden hidden state | No module may read/write global variables, module-level mutable state, files, databases, env vars, or network endpoints except through injected adapters | — |

Modules with injected adapters (`DataPlane` with `DataAdapter`, `ExecutionEngine` with `ExecutionAdapter`) are the only permitted side-effect boundary. All other modules are pure.

---

### Item 5 — Research vs Production Separation

**`experiment_engine.md` new invariants:**
- ExperimentEngine may only propose parameters (`scoring_model_id`, `top_n`, `rebalance_freq`) via `ExperimentParams`
- ExperimentEngine may NOT write to any shared state, modify contracts, override scoring logic, or alter execution behavior directly
- Any proposed experiment that changes scoring model or portfolio construction logic must pass full downstream gates (EvaluationEngine → RiskEngine → AuditMonitor) before production promotion
- ExperimentEngine's output is a read-only side-input; downstream modules must not modify `ExperimentParams` fields

**ARCHITECTURE.md additions** — new section `## Research vs Production Separation`:
- ExperimentEngine is the only entry point for parameter/model variation
- Promotion path: ExperimentEngine → ScoringEngine → … → EvaluationEngine (PASS required) → new contract version + ADR

---

### Item 6 — Quant Portfolio Hardening Placeholders

**New optional fields** added to domain objects (all `None` by default; MVP logic ignores them; validate() accepts None):

| Object | New Field(s) | Type | Notes |
|--------|-------------|------|-------|
| `ScoreSet` | `alpha_decay_halflife_days` | `int \| None = None` | Hint: how fast scores lose predictive power |
| `TargetPortfolio` | `estimated_turnover` | `Decimal \| None = None` | One-way turnover estimate vs prior portfolio |
| `TargetPortfolio` | `capacity_flag` | `str \| None = None` | "ok" / "constrained" / "exceeded" |
| `RiskDecision` | `exposure_attribution` | `dict[str, Decimal] \| None = None` | Sector/factor exposures |
| `RiskDecision` | `regime_label` | `str \| None = None` | E.g. "bull" / "bear" / "neutral" (future) |
| `EvaluationReport` | `confidence_interval` | `tuple[Decimal, Decimal] \| None = None` | (lower, upper) PnL CI (stub: None) |
| `EvaluationReport` | `walk_forward_periods` | `int \| None = None` | Number of WF periods used (stub: None) |

**ARCHITECTURE.md additions** — new section `## Quant Extension Points`:
Table listing all future portfolio-grade concerns (alpha decay, turnover cost, transaction cost, liquidity/capacity, exposure attribution, regime-conditioned behavior, confidence/uncertainty, walk-forward evaluation) and which module owns each placeholder.

---

### Item 7 — EvaluationEngine Stub Labeling

**`EvaluationReport` additions** (no field renames — keeps test churn minimal):
```python
is_stub: bool = True
stub_reason: str = "EvaluationReport is a placeholder; pnl/sharpe/max_drawdown are zero pending real fill data and price history"
```

**`EvaluationEngine`:** Sets `is_stub=True` and `stub_reason` explicitly. All numerical fields remain zero.

**`evaluation_engine.md`** — add invariant: "In MVP, `is_stub` is always `True`; real performance metrics require `FillReport` with actual fill prices and historical price series."

**`operator_report.py`:** When rendering `EvaluationReport`, prefix section with `[STUB METRICS — not real performance]` when `is_stub=True`.

---

### Item 8 — AuditMonitor Typed Input

**New domain object** `OrchestratorRunRecord` (added to `domain/objects.py`):
```python
@dataclass
class OrchestratorRunRecord:
    run_mode: str
    tickers: list[str]
    pipeline_hashes: dict[str, str]  # must contain all required keys
```

**`audit_monitor.assemble_audit_record()` new signature:**
```python
def assemble_audit_record(
    evaluation_report: EvaluationReport,
    run_record: OrchestratorRunRecord,
) -> AuditRecord
```
Replaces the loose `pipeline_hashes: dict[str, str], run_mode: str, tickers: list[str]` params.

**`orchestrator.py`:** Constructs `OrchestratorRunRecord` before calling `assemble_audit_record`.

**Required keys in pipeline_hashes** — updated from 9 to 10:
`universe, market_dataset, market_state, experiment_params, score_set, ranked_universe, target_portfolio, risk_decision, execution_intent, execution_result`

---

### Item 9 — Decimal Policy Clarification

**ARCHITECTURE.md additions** — new section `## Decimal vs Float Policy`:

| Domain | Type | Rationale |
|--------|------|-----------|
| Prices (open/high/low/close) | `Decimal` | Exact; broker precision required |
| Portfolio weights | `Decimal` | Sum constraint must be exact to `Decimal("1.0")` |
| Cash, PnL, risk limits | `Decimal` | Monetary; regulatory precision |
| Score values [0,1] | `Decimal` | Used in exact weight computation |
| Sharpe ratio, volatility, correlation | `float` (future) | Statistical; numerical libraries require float; stub zeros are `Decimal` for now |
| Rank/ordinal (intermediate) | `float` (future) | Library output; convert to Decimal at module boundary |

**Boundary rule:** Convert `float → Decimal` at module output using `Decimal(str(value))`. Never call `float()` on a `Decimal` field.

**Current `EvaluationReport.pnl/sharpe/max_drawdown`:** Remain `Decimal` since they are stub zeros. Future real implementation will compute as `float` internally and convert at the boundary — this is documented in the contract and `stub_reason`.

---

### Item 10 — Tests

**`tests/test_hardening.py`** (new file, 8 tests):
1. `test_execution_intent_execution_result_fill_report_are_distinct_types`
2. `test_execution_result_contains_execution_intent`
3. `test_orchestrator_run_record_is_typed_not_dict` — asserts `OrchestratorRunRecord` passed to audit_monitor
4. `test_no_cross_module_imports` — greps src/ to verify no module imports from another module's path (only domain imports permitted)
5. `test_evaluation_report_is_stub_flagged` — `evaluation_report.is_stub == True`
6. `test_pipeline_hashes_has_10_keys` — updated from 9 to 10
7. `test_fill_report_mirrors_intent_orders_in_stub` — stub FillReport matches ExecutionIntent orders
8. `test_e2e_with_hardened_pipeline_passes` — full run() call succeeds with new objects

**Updated existing tests:**
- `test_domain.py` — add tests for `ExecutionResult`, `FillReport`, `Fill`, `OrchestratorRunRecord`; add `is_stub` assertion on `EvaluationReport`; add tests for new optional quant fields
- `test_execution_engine.py` — expect `ExecutionResult` return type; verify `execution_result.execution_intent` is set
- `test_evaluation_engine.py` — pass `ExecutionResult` instead of `ExecutionIntent`; assert `is_stub=True` in output
- `test_audit_monitor.py` — pass `OrchestratorRunRecord` instead of loose dict/params
- `test_smoke.py` — update full pipeline assertion to check `execution_result.params_hash` in `pipeline_hashes`

---

## Execution Order

Dependencies must be satisfied before downstream changes:

1. **domain/objects.py** — add all new objects and fields (no deps)
2. **domain/adapters.py** — update `ExecutionAdapter.submit()` return type
3. **domain/stubs.py** — update `StubExecutionAdapter.submit()` to return `ExecutionResult`
4. **execution_engine.py** — return `ExecutionResult`
5. **evaluation_engine.py** — accept `ExecutionResult`, create `FillReport`
6. **audit_monitor.py** — accept `OrchestratorRunRecord`
7. **orchestrator.py** — wire `OrchestratorRunRecord`, update pipeline_hashes keys
8. **operator_report.py** — add stub label
9. **All contracts** — add version headers; update 4 affected contracts
10. **ARCHITECTURE.md** — add all new sections
11. **docs/adr/0002** — write execution lifecycle ADR
12. **Tests** — update all affected tests; write test_hardening.py
13. **HARDENING_SUMMARY.md** — final summary

---

## Key File Paths

| File | Change Type |
|------|------------|
| `src/portfolio_ninja/domain/objects.py` | Add: ExecutionResult, FillReport, Fill, OrchestratorRunRecord; Modify: EvaluationReport (is_stub, stub_reason), ScoreSet, TargetPortfolio, RiskDecision |
| `src/portfolio_ninja/domain/adapters.py` | Modify: ExecutionAdapter.submit() → ExecutionResult |
| `src/portfolio_ninja/domain/stubs.py` | Modify: StubExecutionAdapter.submit() returns ExecutionResult |
| `src/portfolio_ninja/execution_engine/execution_engine.py` | Modify: return ExecutionResult |
| `src/portfolio_ninja/evaluation_engine/evaluation_engine.py` | Modify: accept ExecutionResult, create FillReport, set is_stub=True |
| `src/portfolio_ninja/audit_monitor/audit_monitor.py` | Modify: accept OrchestratorRunRecord |
| `src/portfolio_ninja/orchestrator.py` | Modify: construct OrchestratorRunRecord; update pipeline_hashes (10 keys) |
| `src/portfolio_ninja/operator_report.py` | Modify: add [STUB METRICS] label |
| `docs/contracts/*.md` (all 12) | Add: version header |
| `docs/contracts/execution_engine.md` | Modify: output is ExecutionResult |
| `docs/contracts/evaluation_engine.md` | Modify: input is ExecutionResult, FillReport created internally, is_stub invariant |
| `docs/contracts/audit_monitor.md` | Modify: input is OrchestratorRunRecord; 10 required keys |
| `docs/contracts/experiment_engine.md` | Modify: research/production separation invariants |
| `docs/contracts/domain_objects.md` | Modify: add all new objects |
| `docs/ARCHITECTURE.md` | Add: 5 new sections |
| `docs/adr/0002-execution-lifecycle-and-fill-model.md` | Create |
| `tests/test_hardening.py` | Create (8 tests) |
| `tests/test_domain.py` | Modify (new object tests) |
| `tests/test_execution_engine.py` | Modify (ExecutionResult return type) |
| `tests/test_evaluation_engine.py` | Modify (ExecutionResult input) |
| `tests/test_audit_monitor.py` | Modify (OrchestratorRunRecord) |
| `tests/test_smoke.py` | Modify (10 pipeline_hashes keys) |
| `HARDENING_SUMMARY.md` | Create |

---

## Verification

After implementation:

```
conda run -n base python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

Expected:
- All tests pass (≥ previous 97% coverage)
- `test_hardening.py` all 8 tests pass
- `run_e2e_demo.py` still prints E2E TEST: PASS with 10 pipeline hashes

Manual spot-checks:
- `execution_result.execution_intent` is not None
- `evaluation_report.is_stub == True`
- `fill_report.is_stub == True`
- Operator report shows `[STUB METRICS]` label
- `audit_record.pipeline_hashes` has exactly 10 keys including `execution_result`
