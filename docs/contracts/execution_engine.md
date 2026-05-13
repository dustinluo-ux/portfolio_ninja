# Contract: ExecutionEngine

## Purpose
Translate an approved `RiskDecision` into a list of `Order` objects; submit via the injected `ExecutionAdapter`; emit a typed, lineage-annotated `ExecutionIntent` that documents either the submitted orders or the rejection.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `risk_decision` | `RiskDecision` | RiskEngine | yes | Approval status and final weights; must have `validation_status == "valid"` |
| `adapter` | `ExecutionAdapter` | Orchestrator (dependency injection) | yes | Concrete implementation of `ExecutionAdapter` ABC; in MVP this is `StubExecutionAdapter` |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `execution_intent` | `ExecutionIntent` | EvaluationEngine | Orders submitted (or empty list if rejected); adapter identity; run mode; full lineage |

## Dependencies
- `domain` — provides `RiskDecision`, `ExecutionIntent`, `Order`, and `ExecutionAdapter` types
- `RiskEngine` — must have approved contract; provides `RiskDecision`

## Invariants
- If `risk_decision.approved == True`: `execution_intent.orders` is non-empty (one `Order` per ticker in `risk_decision.weights`, direction = `"buy"`, order_type = `"market"`, quantity = weight expressed as `Decimal` fraction)
- If `risk_decision.approved == False`: `execution_intent.orders` is an empty list; `execution_intent.reason_codes` contains `"risk_rejected"` plus all `risk_decision.reason_codes`; no adapter call is made; no error raised
- All `Order.quantity` values are `decimal.Decimal`; never `float`
- `execution_intent.adapter_id == adapter.__class__.__name__`
- `execution_intent.run_mode` is propagated from `risk_decision` lineage (stored in orchestrator context; passed through as string); must be one of `{"backtest", "paper", "live"}`
- `ExecutionAdapter.submit()` is called exactly once with the full `ExecutionIntent` when `approved == True`; raises `ExecutionError` (wrapping adapter exception) on failure
- `execution_intent.validation_status == "valid"` on successful exit (even when orders are empty due to rejection)
- `execution_intent.as_of_date == risk_decision.as_of_date`
- `execution_intent.params_hash` is SHA-256 hex of `(risk_decision.params_hash, adapter.__class__.__name__)`
- `execution_intent.reason_codes` is an empty list on approved-and-submitted success
- Monetary values: Decimal only, never float
- No silent fallback on adapter failure; fail-loud

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| `ExecutionAdapter.submit()` raises any exception | M | H | Catches and re-raises as `ExecutionError` with original exception as cause; `ExecutionIntent` is NOT emitted on this path |
| `risk_decision.approved == False` | M | M | Emits `ExecutionIntent` with empty orders and `reason_codes`; no exception; no adapter call |
| `risk_decision.weights` is empty when `approved == True` | L | H | Raises `ValueError("RiskDecision.weights is empty but approved is True")` |

## Tests Required
- [ ] `test_execution_engine_approved_decision_produces_non_empty_orders`
- [ ] `test_execution_engine_rejected_decision_produces_empty_orders`
- [ ] `test_execution_engine_rejected_decision_does_not_call_adapter`
- [ ] `test_execution_engine_adapter_exception_propagates_as_execution_error`
- [ ] `test_execution_engine_adapter_id_is_class_name_of_adapter`
- [ ] `test_execution_engine_all_order_quantities_are_decimal`
- [ ] `test_execution_engine_validation_status_is_valid_on_success`
- [ ] `test_execution_engine_reason_codes_include_risk_rejection_reason_when_rejected`
- [ ] `test_execution_engine_integration_stub_adapter_logs_intent`

## Acceptance Criteria
- [ ] Approved `RiskDecision` produces `ExecutionIntent` with one `Order` per ticker, submitted via adapter
- [ ] Rejected `RiskDecision` produces `ExecutionIntent` with empty orders; adapter is not called
- [ ] Adapter exceptions propagate as `ExecutionError`; no silent swallowing
- [ ] `execution_intent.adapter_id == adapter.__class__.__name__`
- [ ] All `Order.quantity` values are `Decimal`; no `float` anywhere in module code
- [ ] `validation_status == "valid"` on success (including rejection path)

## Upstream Providers
- RiskEngine (provides `RiskDecision`)
- Orchestrator (injects `ExecutionAdapter` implementation)

## Downstream Consumers
- EvaluationEngine (consumes `ExecutionIntent`)
