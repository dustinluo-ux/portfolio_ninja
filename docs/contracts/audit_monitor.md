# Contract: AuditMonitor

## Purpose
Assemble full pipeline lineage by collecting `params_hash` values from all 9 upstream pipeline objects; emit a typed, terminal `AuditRecord` that provides complete auditability and reproducibility for the cycle.

## Status
implemented

## Inputs
| Name | Type | Source | Required | Description |
|------|------|--------|----------|-------------|
| `evaluation_report` | `EvaluationReport` | EvaluationEngine | yes | Carries `cycle_id`, `params_hash`, `as_of_date`; must have `validation_status == "valid"` and non-empty `cycle_id` |
| `pipeline_hashes` | `dict[str, str]` | Orchestrator | yes | Map of pipeline object name to `params_hash`; must contain exactly the 9 keys listed below |

## Outputs
| Name | Type | Consumer | Description |
|------|------|----------|-------------|
| `audit_record` | `AuditRecord` | Terminal (no downstream pipeline module) | Complete lineage record for the cycle; cycle_id, run_mode, tickers, all pipeline hashes, and UTC completion timestamp |

## Dependencies
- `domain` — provides `EvaluationReport` and `AuditRecord` types
- `EvaluationEngine` — must have approved contract; provides `EvaluationReport`

## Invariants
- `audit_record.pipeline_hashes` must contain entries for all 9 pipeline objects:
  `"universe"`, `"market_dataset"`, `"market_state"`, `"experiment_params"`, `"score_set"`, `"ranked_universe"`, `"target_portfolio"`, `"risk_decision"`, `"execution_intent"`
- Any missing key raises `AuditIncompleteError(f"Missing pipeline hash for: {missing_keys}")` listing all absent keys
- `audit_record.cycle_id == evaluation_report.cycle_id`; `cycle_id` has a single source (`evaluation_report`) — a mismatch scenario is structurally unimplementable in the MVP single-source design; the invariant is satisfied by construction
- `audit_record.completed_at` is a UTC `datetime` set at the moment `AuditRecord` is constructed (not inherited from upstream)
- `audit_record.run_mode` is propagated from orchestrator context (same value as `Universe.run_mode` for the cycle)
- `audit_record.tickers` is the canonical ticker list for the cycle (same as `Universe.tickers` after deduplication)
- `audit_record.validation_status == "valid"` on successful exit
- `audit_record.reason_codes` is an empty list on success
- All values in `audit_record.pipeline_hashes` are non-empty hex strings; empty string raises `AuditIncompleteError`
- Monetary values: Decimal only, never float
- No external I/O in MVP; purely in-memory assembly
- File writes: if audit record is persisted to disk (future enhancement), atomic pattern (.tmp -> os.replace) must be used

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| One or more keys missing from `pipeline_hashes` | M | H | Raises `AuditIncompleteError` listing all missing keys; no partial `AuditRecord` emitted |
| `cycle_id` mismatch | N/A | — | Not applicable: single-source design; `cycle_id` comes only from `evaluation_report`; mismatch is architecturally impossible in MVP |
| A `params_hash` value in `pipeline_hashes` is an empty string | L | H | Raises `AuditIncompleteError(f"Empty params_hash for pipeline object: {key}")` |
| `evaluation_report.validation_status != "valid"` | L | M | Raises `AuditIncompleteError("EvaluationReport is not valid")` |

## Tests Required
- [ ] `test_audit_monitor_complete_pipeline_hashes_returns_valid_audit_record`
- [ ] `test_audit_monitor_missing_single_hash_raises_audit_incomplete_error`
- [ ] `test_audit_monitor_missing_multiple_hashes_lists_all_in_error`
- [ ] `test_audit_monitor_cycle_id_distinct_values_propagated_correctly` (replaces mismatch/raise test; single-source design makes mismatch unimplementable)
- [ ] `test_audit_monitor_empty_params_hash_value_raises_audit_incomplete_error`
- [ ] `test_audit_monitor_completed_at_is_utc_datetime`
- [ ] `test_audit_monitor_pipeline_hashes_contains_all_nine_keys`
- [ ] `test_audit_monitor_validation_status_is_valid_on_success`
- [ ] `test_audit_monitor_cycle_id_propagated_from_evaluation_report`

## Acceptance Criteria
- [ ] Returns `AuditRecord` with all 9 pipeline hash keys present and non-empty
- [ ] `audit_record.cycle_id == evaluation_report.cycle_id`
- [ ] `audit_record.completed_at` is a UTC `datetime` (not None, not a date)
- [ ] Raises `AuditIncompleteError` for any missing, empty, or mismatched hash
- [ ] `validation_status == "valid"` on success
- [ ] No `float` anywhere in module code
- [ ] `audit_record.pipeline_hashes` contains exactly these keys: `"universe"`, `"market_dataset"`, `"market_state"`, `"experiment_params"`, `"score_set"`, `"ranked_universe"`, `"target_portfolio"`, `"risk_decision"`, `"execution_intent"`

## Upstream Providers
- EvaluationEngine (provides `EvaluationReport`)
- Orchestrator (provides `pipeline_hashes: dict[str, str]` assembled from all upstream domain objects)

## Downstream Consumers
- Terminal — `AuditRecord` is the final output of the canonical decision path; no downstream pipeline module
