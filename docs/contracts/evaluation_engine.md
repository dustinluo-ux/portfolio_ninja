# Contract: EvaluationEngine

## Purpose
Compute cycle performance metrics (PnL, Sharpe ratio, max drawdown) from an `ExecutionIntent`; emit a typed, lineage-annotated `EvaluationReport`; in the MVP stub all metrics are `Decimal("0")` as no real execution data is available.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `execution_intent` | `ExecutionIntent` | ExecutionEngine | yes | Orders submitted (or empty); must have `validation_status == "valid"` and a non-empty `cycle_id` derivable from its lineage |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `evaluation_report` | `EvaluationReport` | AuditMonitor | Cycle PnL, Sharpe, max drawdown, cycle_id, and full lineage |

## Dependencies
- `domain` — provides `ExecutionIntent` and `EvaluationReport` types
- `ExecutionEngine` — must have approved contract; provides `ExecutionIntent`

## Invariants
- `evaluation_report.cycle_id` is non-empty; derived from `execution_intent.params_hash` (first 16 hex chars) if not externally provided; raises `ValueError("cycle_id must not be empty")` if derivation fails
- `evaluation_report.pnl` is `decimal.Decimal`; MVP stub value = `Decimal("0")`
- `evaluation_report.sharpe` is `decimal.Decimal`; MVP stub value = `Decimal("0")`
- `evaluation_report.max_drawdown` is `decimal.Decimal`; MVP stub value = `Decimal("0")`
- Empty `execution_intent.orders` (rejected portfolio) produces valid `EvaluationReport` with zero metrics and `reason_codes` populated with `"no_orders_executed"`; not an error
- `evaluation_report.validation_status == "valid"` on successful exit
- `evaluation_report.as_of_date == execution_intent.as_of_date`
- `evaluation_report.params_hash` is SHA-256 hex of `(execution_intent.params_hash, "evaluation_engine_v1")`
- `evaluation_report.reason_codes` is `["no_orders_executed"]` when orders are empty; otherwise empty list
- Monetary values: Decimal only, never float
- No external I/O in MVP; purely in-memory stub computation

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| `execution_intent.orders` is empty | M | L | Emits `EvaluationReport` with zero metrics and `reason_codes = ["no_orders_executed"]`; no error |
| `cycle_id` cannot be derived (empty `params_hash`) | L | H | Raises `ValueError("cycle_id must not be empty — execution_intent.params_hash is missing")` |
| Future real metric computation raises (e.g., division by zero in Sharpe) | L | M | Raises `EvaluationError` with full context; not a concern in MVP stub |

## Tests Required
- [ ] `test_evaluation_engine_non_empty_orders_returns_evaluation_report`
- [ ] `test_evaluation_engine_empty_orders_returns_zero_metrics_report`
- [ ] `test_evaluation_engine_empty_orders_populates_reason_codes_no_orders`
- [ ] `test_evaluation_engine_cycle_id_is_non_empty`
- [ ] `test_evaluation_engine_pnl_sharpe_max_drawdown_are_decimal`
- [ ] `test_evaluation_engine_stub_metrics_are_zero`
- [ ] `test_evaluation_engine_validation_status_is_valid_on_success`
- [ ] `test_evaluation_engine_as_of_date_propagated_from_execution_intent`

## Acceptance Criteria
- [ ] Returns `EvaluationReport` with `cycle_id`, `pnl`, `sharpe`, `max_drawdown` all populated
- [ ] MVP stub values: `pnl == Decimal("0")`, `sharpe == Decimal("0")`, `max_drawdown == Decimal("0")`
- [ ] Empty orders path returns valid report (not an error) with `reason_codes = ["no_orders_executed"]`
- [ ] `cycle_id` is non-empty; derived from `execution_intent.params_hash`
- [ ] All metric fields are `Decimal`; no `float` anywhere in module code
- [ ] `validation_status == "valid"` on success

## Upstream Providers
- ExecutionEngine (provides `ExecutionIntent`)

## Downstream Consumers
- AuditMonitor (consumes `EvaluationReport`)
