import hashlib
from decimal import Decimal

from portfolio_ninja.config.params_loader import load_params
from portfolio_ninja.domain.exceptions import UnknownModelError
from portfolio_ninja.domain.objects import ExperimentParams, MarketState, ScoreSet

_ZERO = Decimal("0")
_ONE = Decimal("1")
_THOUSAND = Decimal("1000")
_HUNDRED = Decimal("100")

_p = load_params()["scoring"]
_HALF = Decimal(str(_p["degenerate_score"]))
_W_MOM = Decimal(str(_p["w_momentum"]))
_W_VOL = Decimal(str(_p["w_volatility"]))
_W_RSI = Decimal(str(_p["w_rsi"]))
del _p

_REGISTERED_MODELS = {"stub_v1", "technical_composite_v1"}


def _stub_score(ticker: str) -> Decimal:
    return Decimal(str(abs(hash(ticker)) % 1000)) / _THOUSAND


def _minmax_normalize(values: list[Decimal]) -> list[Decimal]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [_HALF] * len(values)
    span = hi - lo
    return [(v - lo) / span for v in values]


def _technical_composite_score(market_state: MarketState) -> dict[str, Decimal]:
    tickers = list(market_state.features.keys())
    momentums = [market_state.features[t].momentum_20d for t in tickers]
    vols = [market_state.features[t].volatility_20d for t in tickers]
    rsis = [market_state.features[t].rsi_14 / _HUNDRED for t in tickers]

    nm = _minmax_normalize(momentums)
    nv = _minmax_normalize(vols)
    nr = _minmax_normalize(rsis)

    scores: dict[str, Decimal] = {}
    for i, ticker in enumerate(tickers):
        raw = _W_MOM * nm[i] + _W_VOL * (_ONE - nv[i]) + _W_RSI * nr[i]
        scores[ticker] = max(_ZERO, min(_ONE, raw))
    return scores


def score_tickers(market_state: MarketState, experiment_params: ExperimentParams) -> ScoreSet:
    model_id = experiment_params.scoring_model_id
    if model_id not in _REGISTERED_MODELS:
        raise UnknownModelError(f"Unknown model: {model_id}")

    if model_id == "technical_composite_v1":
        scores = _technical_composite_score(market_state)
    else:
        scores = {}
        for ticker in market_state.features:
            scores[ticker] = _stub_score(ticker)

    for ticker, score in scores.items():
        if score < _ZERO or score > _ONE:
            raise ValueError(f"Score out of range for ticker {ticker}: {score}")

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
