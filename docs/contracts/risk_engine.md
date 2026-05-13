# Contract: RiskEngine

## Purpose
Validate `TargetPortfolio` against risk rules (weight-sum integrity, no-leverage, concentration limits); emit a typed, lineage-annotated `RiskDecision` that either approves or rejects the portfolio.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `target_portfolio` | `TargetPortfolio` | PortfolioConstructionEngine | yes | Equal-weight portfolio; must have `validation_status == "valid"` and weights summing to `Decimal("1.0")` |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `risk_decision` | `RiskDecision` | ExecutionEngine | Approval status, final weights (identical to input in MVP stub), adjustments list, and full lineage |

## Dependencies
- `domain` — provides `TargetPortfolio` and `RiskDecision` types
- `PortfolioConstructionEngine` — must have approved contract; provides `TargetPortfolio`

## Invariants
- `risk_decision.weights` mirrors `target_portfolio.weights` exactly (no adjustment in MVP stub)
- `sum(risk_decision.weights.values()) == Decimal("1.0")` always; checked before emitting; raises `WeightSumError` if not (not correctable)
- No individual weight exceeds `Decimal("0.25")` (4x concentration limit, 25% max per ticker); if exceeded, `risk_decision.approved = False` and reason added to `risk_decision.reason_codes`
- `risk_decision.approved == True` only if ALL of: weight sum == `Decimal("1.0")` AND no individual weight > `Decimal("0.25")`
- `risk_decision.adjustments` is an empty list in MVP stub (no corrective adjustments; reject-only)
- All weight values are `decimal.Decimal`; never `float`
- `risk_decision.validation_status == "valid"` on successful exit (even if `approved == False`)
- `risk_decision.as_of_date == target_portfolio.as_of_date`
- `risk_decision.params_hash` is SHA-256 hex of `(target_portfolio.params_hash, "risk_engine_v1")`
- `risk_decision.reason_codes` populated with specific rule violations when `approved == False`
- Net exposure = sum of all weights = `Decimal("1.0")`; satisfies no-leverage constraint (CASE_FACTS Decision 16)
- Monetary values: Decimal only, never float
- No external I/O; purely in-memory rule evaluation

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| `sum(target_portfolio.weights.values()) != Decimal("1.0")` | L | H | Raises `WeightSumError("Portfolio weights do not sum to 1.0")` immediately; not correctable |
| Individual weight > `Decimal("0.25")` | M | M | Sets `risk_decision.approved = False`; adds `"concentration_limit_exceeded:{ticker}:{weight}"` to `reason_codes`; emits `RiskDecision` (no exception) |
| Empty `target_portfolio.weights` | L | H | Raises `ValueError("TargetPortfolio.weights must not be empty")` |

## Tests Required
- [ ] `test_risk_engine_valid_portfolio_returns_approved_risk_decision`
- [ ] `test_risk_engine_concentration_limit_exceeded_sets_approved_false`
- [ ] `test_risk_engine_concentration_limit_exceeded_populates_reason_codes`
- [ ] `test_risk_engine_weight_sum_not_one_raises_weight_sum_error`
- [ ] `test_risk_engine_empty_weights_raises_value_error`
- [ ] `test_risk_engine_risk_decision_weights_match_target_portfolio_weights`
- [ ] `test_risk_engine_all_weights_are_decimal`
- [ ] `test_risk_engine_validation_status_is_valid_on_success`
- [ ] `test_risk_engine_approved_true_only_when_all_checks_pass`

## Acceptance Criteria
- [ ] Returns `RiskDecision` with `approved == True` when all risk rules pass
- [ ] Returns `RiskDecision` with `approved == False` and non-empty `reason_codes` when concentration limit exceeded
- [ ] Raises `WeightSumError` (not returns) when weight sum != `Decimal("1.0")`
- [ ] `risk_decision.weights` is identical to `target_portfolio.weights` in MVP stub
- [ ] All weight values are `Decimal`; no `float` anywhere in module code
- [ ] `validation_status == "valid"` on success (including when `approved == False`)

## Upstream Providers
- PortfolioConstructionEngine (provides `TargetPortfolio`)

## Downstream Consumers
- ExecutionEngine (consumes `RiskDecision`)
