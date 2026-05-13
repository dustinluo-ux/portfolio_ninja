import hashlib

from portfolio_ninja.domain.adapters import ExecutionAdapter
from portfolio_ninja.domain.exceptions import ExecutionError
from portfolio_ninja.domain.objects import ExecutionIntent, Order, RiskDecision


def execute_orders(
    risk_decision: RiskDecision,
    adapter: ExecutionAdapter,
    run_mode: str,
) -> ExecutionIntent:
    adapter_id = adapter.__class__.__name__
    params_hash = hashlib.sha256(
        f"{risk_decision.params_hash}|{adapter_id}".encode()
    ).hexdigest()

    if not risk_decision.approved:
        reason_codes = ["risk_rejected"] + list(risk_decision.reason_codes)
        return ExecutionIntent(
            orders=[],
            adapter_id=adapter_id,
            run_mode=run_mode,
            as_of_date=risk_decision.as_of_date,
            params_hash=params_hash,
            validation_status="valid",
            reason_codes=reason_codes,
        )

    if not risk_decision.weights:
        raise ValueError("RiskDecision.weights is empty but approved is True")

    orders = [
        Order(
            ticker=ticker,
            direction="buy",
            quantity=weight,
            order_type="market",
        )
        for ticker, weight in risk_decision.weights.items()
    ]

    intent = ExecutionIntent(
        orders=orders,
        adapter_id=adapter_id,
        run_mode=run_mode,
        as_of_date=risk_decision.as_of_date,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=[],
    )

    try:
        adapter.submit(intent)
    except Exception as exc:
        raise ExecutionError(str(exc)) from exc

    return intent
