import hashlib
from decimal import Decimal

from portfolio_ninja.domain.exceptions import UnknownModelError
from portfolio_ninja.domain.objects import ExperimentParams, MarketState, ScoreSet

_ZERO = Decimal("0")
_ONE = Decimal("1")
_THOUSAND = Decimal("1000")

_REGISTERED_MODELS = {"stub_v1"}


def _stub_score(ticker: str) -> Decimal:
    return Decimal(str(abs(hash(ticker)) % 1000)) / _THOUSAND


def score_tickers(market_state: MarketState, experiment_params: ExperimentParams) -> ScoreSet:
    model_id = experiment_params.scoring_model_id
    if model_id not in _REGISTERED_MODELS:
        raise UnknownModelError(f"Unknown model: {model_id}")

    scores: dict[str, Decimal] = {}
    for ticker in market_state.features:
        score = _stub_score(ticker)
        if score < _ZERO or score > _ONE:
            raise ValueError(f"Score out of range for ticker {ticker}: {score}")
        scores[ticker] = score

    params_hash = hashlib.sha256(
        f"{market_state.params_hash}|{experiment_params.params_hash}".encode()
    ).hexdigest()

    return ScoreSet(
        scores=scores,
        model_id=model_id,
        as_of_date=market_state.as_of_date,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=[],
    )
