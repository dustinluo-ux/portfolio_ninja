import hashlib
from decimal import Decimal

from portfolio_ninja.domain.objects import ExperimentParams, RankedUniverse, TargetPortfolio

_ONE = Decimal("1")


def construct_portfolio(
    ranked_universe: RankedUniverse,
    experiment_params: ExperimentParams,
) -> TargetPortfolio:
    if not ranked_universe.ranked:
        raise ValueError("RankedUniverse must not be empty")
    if experiment_params.top_n < 1:
        raise ValueError("top_n must be >= 1")

    reason_codes: list[str] = []
    available = len(ranked_universe.ranked)
    n = min(experiment_params.top_n, available)
    if n < experiment_params.top_n:
        reason_codes.append(f"top_n_capped:{n}")

    selected = [ticker for ticker, _ in ranked_universe.ranked[:n]]
    base_weight = _ONE / Decimal(str(n))
    weights = {ticker: base_weight for ticker in selected}

    # Adjust first ticker to absorb rounding residual for exact sum
    total = sum(weights.values())
    residual = _ONE - total
    if residual != Decimal("0"):
        weights[selected[0]] += residual

    params_hash = hashlib.sha256(
        f"{ranked_universe.params_hash}|{experiment_params.params_hash}".encode()
    ).hexdigest()

    return TargetPortfolio(
        weights=weights,
        as_of_date=ranked_universe.as_of_date,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=reason_codes,
    )
