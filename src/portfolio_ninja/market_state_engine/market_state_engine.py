import hashlib
from decimal import Decimal

from portfolio_ninja.domain.exceptions import DataIntegrityError, InsufficientDataError
from portfolio_ninja.domain.objects import MarketDataset, MarketState, TickerFeatures

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


def _momentum_20d(closes: list[Decimal], ticker: str) -> Decimal:
    if len(closes) < 21:
        raise InsufficientDataError(
            f"insufficient_bars:{ticker}:needed:21:got:{len(closes)}"
        )
    prior = closes[-21]
    if prior == _ZERO:
        raise DataIntegrityError(f"close price is zero for ticker {ticker}")
    return (closes[-1] - prior) / prior


def _volatility_20d(closes: list[Decimal], ticker: str) -> Decimal:
    if len(closes) < 21:
        raise InsufficientDataError(
            f"insufficient_bars:{ticker}:needed:21:got:{len(closes)}"
        )
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(len(closes) - 20, len(closes))
        if closes[i - 1] != _ZERO
    ]
    n = len(returns)
    if n == 0:
        return _ZERO
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / n
    if variance <= _ZERO:
        return _ZERO
    std = variance.sqrt()
    return std.quantize(Decimal("0.000001"))


def _rsi_14(closes: list[Decimal], ticker: str) -> tuple[Decimal, bool]:
    """Returns (rsi, was_clamped)."""
    if len(closes) < 15:
        raise InsufficientDataError(
            f"insufficient_bars:{ticker}:needed:15:got:{len(closes)}"
        )
    changes = [closes[i] - closes[i - 1] for i in range(len(closes) - 14, len(closes))]
    gains = [c if c > _ZERO else _ZERO for c in changes]
    losses = [-c if c < _ZERO else _ZERO for c in changes]
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    if avg_loss == _ZERO:
        rsi = _HUNDRED
    else:
        rs = avg_gain / avg_loss
        rsi = _HUNDRED - (_HUNDRED / (1 + rs))
    clamped = False
    if rsi < _ZERO:
        rsi = _ZERO
        clamped = True
    if rsi > _HUNDRED:
        rsi = _HUNDRED
        clamped = True
    return rsi.quantize(Decimal("0.0001")), clamped


def compute_market_state(dataset: MarketDataset) -> MarketState:
    features: dict[str, TickerFeatures] = {}
    reason_codes: list[str] = []

    for ticker, ticker_data in dataset.data.items():
        closes = [bar.close for bar in ticker_data.ohlcv]
        mom = _momentum_20d(closes, ticker)
        vol = _volatility_20d(closes, ticker)
        rsi, clamped = _rsi_14(closes, ticker)
        if clamped:
            reason_codes.append(f"rsi_clamped:{ticker}")
        features[ticker] = TickerFeatures(
            momentum_20d=mom,
            volatility_20d=vol,
            rsi_14=rsi,
        )

    params_hash = hashlib.sha256(
        f"{dataset.params_hash}|market_state_engine_v1".encode()
    ).hexdigest()

    return MarketState(
        features=features,
        as_of_date=dataset.as_of_date,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=reason_codes,
    )
