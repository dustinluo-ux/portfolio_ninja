import hashlib
from decimal import Decimal

from portfolio_ninja.config.params_loader import load_params
from portfolio_ninja.domain.exceptions import WeightSumError
from portfolio_ninja.domain.objects import RiskDecision, TargetPortfolio

_ONE = Decimal("1.0")
_CONCENTRATION_LIMIT = Decimal(str(load_params()["risk"]["concentration_limit"]))


def evaluate_risk(target_portfolio: TargetPortfolio) -> RiskDecision:
    if not target_portfolio.weights:
        raise ValueError("TargetPortfolio.weights must not be empty")

    total = sum(target_portfolio.weights.values())
    if total != _ONE:
        raise WeightSumError("Portfolio weights do not sum to 1.0")

    reason_codes: list[str] = []
    approved = True
    for ticker, weight in target_portfolio.weights.items():
        if weight > _CONCENTRATION_LIMIT:
            approved = False
            reason_codes.append(f"concentration_limit_exceeded:{ticker}:{weight}")

    params_hash = hashlib.sha256(
        f"{target_portfolio.params_hash}|risk_engine_v1".encode()
    ).hexdigest()

    return RiskDecision(
        approved=approved,
        weights=dict(target_portfolio.weights),
        adjustments=[],
        as_of_date=target_portfolio.as_of_date,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=reason_codes,
    )
