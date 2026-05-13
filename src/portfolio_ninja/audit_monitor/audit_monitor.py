from datetime import datetime, timezone

from portfolio_ninja.domain.exceptions import AuditIncompleteError
from portfolio_ninja.domain.objects import AuditRecord, EvaluationReport

_REQUIRED_HASH_KEYS = frozenset({
    "universe",
    "market_dataset",
    "market_state",
    "experiment_params",
    "score_set",
    "ranked_universe",
    "target_portfolio",
    "risk_decision",
    "execution_intent",
})


def assemble_audit_record(
    evaluation_report: EvaluationReport,
    pipeline_hashes: dict[str, str],
    run_mode: str,
    tickers: list[str],
) -> AuditRecord:
    if evaluation_report.validation_status != "valid":
        raise AuditIncompleteError("EvaluationReport is not valid")

    missing = _REQUIRED_HASH_KEYS - set(pipeline_hashes.keys())
    if missing:
        raise AuditIncompleteError(
            f"Missing pipeline hash for: {sorted(missing)}"
        )

    for key, value in pipeline_hashes.items():
        if not value:
            raise AuditIncompleteError(
                f"Empty params_hash for pipeline object: {key}"
            )

    return AuditRecord(
        cycle_id=evaluation_report.cycle_id,
        run_mode=run_mode,
        tickers=list(tickers),
        pipeline_hashes=dict(pipeline_hashes),
        completed_at=datetime.now(tz=timezone.utc),
        validation_status="valid",
        reason_codes=[],
    )
