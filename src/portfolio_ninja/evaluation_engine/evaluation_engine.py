import hashlib
from decimal import Decimal

from portfolio_ninja.domain.objects import EvaluationReport, ExecutionIntent

_ZERO = Decimal("0")


def evaluate_cycle(execution_intent: ExecutionIntent) -> EvaluationReport:
    if not execution_intent.params_hash:
        raise ValueError(
            "cycle_id must not be empty — execution_intent.params_hash is missing"
        )

    cycle_id = execution_intent.params_hash[:16]
    reason_codes: list[str] = []
    if not execution_intent.orders:
        reason_codes.append("no_orders_executed")

    params_hash = hashlib.sha256(
        f"{execution_intent.params_hash}|evaluation_engine_v1".encode()
    ).hexdigest()

    return EvaluationReport(
        cycle_id=cycle_id,
        pnl=_ZERO,
        sharpe=_ZERO,
        max_drawdown=_ZERO,
        as_of_date=execution_intent.as_of_date,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=reason_codes,
    )
