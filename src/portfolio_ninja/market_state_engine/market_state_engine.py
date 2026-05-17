import hashlib
from decimal import Decimal

from portfolio_ninja.config.params_loader import load_params
from portfolio_ninja.domain.exceptions import DataIntegrityError, InsufficientDataError
from portfolio_ninja.domain.objects import MarketDataset, MarketState, TickerFeatures

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_LN2 = Decimal("0.693147180559945")  # ln(2), pre-computed

_p = load_params()["market_state"]
_MOMENTUM_PERIOD: int = _p["momentum_period"]
_RSI_PERIOD: int = _p["rsi_period"]
_SMA_REGIME_PERIOD: int = _p["sma_regime_period"]
_EWMA_SPAN: int = _p["ewma_span"]
_EWMA_ALPHA = Decimal("2") / Decimal(str(_EWMA_SPAN + 1))
_EWMA_LAMBDA = Decimal("1") - _EWMA_ALPHA
_SCSI_BASELINE = Decimal(str(_p["scsi_sentiment_baseline"]))
del _p


def _momentum_20d(closes: list[Decimal], ticker: str) -> Decimal:
    if len(closes) < _MOMENTUM_PERIOD + 1:
        raise InsufficientDataError(
            f"insufficient_bars:{ticker}:needed:{_MOMENTUM_PERIOD + 1}:got:{len(closes)}"
        )
    prior = closes[-(_MOMENTUM_PERIOD + 1)]
    if prior == _ZERO:
        raise DataIntegrityError(f"close price is zero for ticker {ticker}")
    return (closes[-1] - prior) / prior


def _volatility_20d(closes: list[Decimal], ticker: str) -> Decimal:
    if len(closes) < _MOMENTUM_PERIOD + 1:
        raise InsufficientDataError(
            f"insufficient_bars:{ticker}:needed:{_MOMENTUM_PERIOD + 1}:got:{len(closes)}"
        )
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(len(closes) - _MOMENTUM_PERIOD, len(closes))
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
    if len(closes) < _RSI_PERIOD + 1:
        raise InsufficientDataError(
            f"insufficient_bars:{ticker}:needed:{_RSI_PERIOD + 1}:got:{len(closes)}"
        )
    changes = [closes[i] - closes[i - 1] for i in range(len(closes) - _RSI_PERIOD, len(closes))]
    gains = [c if c > _ZERO else _ZERO for c in changes]
    losses = [-c if c < _ZERO else _ZERO for c in changes]
    avg_gain = sum(gains) / _RSI_PERIOD
    avg_loss = sum(losses) / _RSI_PERIOD
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


def _volatility_ewma(closes: list[Decimal], ticker: str) -> Decimal:
    """EWMA std dev of daily returns, span=38 (α=2/39). Mined from pods/pod_core.py."""
    if len(closes) < 2:
        raise InsufficientDataError(
            f"insufficient_bars:{ticker}:needed:2:got:{len(closes)}"
        )
    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] != _ZERO:
            returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
    if not returns:
        return _ZERO
    var = returns[0] ** 2
    for r in returns[1:]:
        var = _EWMA_LAMBDA * var + _EWMA_ALPHA * r ** 2
    if var <= _ZERO:
        return _ZERO
    return var.sqrt().quantize(Decimal("0.000001"))


def _scsi_from_sentiment(news_sentiment: Decimal) -> Decimal:
    """Stress Composite Signal Index. Mined from feature_engineering.py L44-48.
    MVP: article_count=1 → formula simplifies to (sentiment - 0.5) × ln(2)."""
    return ((news_sentiment - _SCSI_BASELINE) * _LN2).quantize(Decimal("0.000001"))


def _regime_signal(dataset: MarketDataset) -> tuple[str, list[str]]:
    """SPY/200-SMA binary regime. Mined from regime_controller.py."""
    spy_td = dataset.regime_data.get("SPY")
    if spy_td is None:
        return ("EXPANSION", ["regime_spy_missing"])
    spy_closes = [bar.close for bar in spy_td.ohlcv]
    if len(spy_closes) < _SMA_REGIME_PERIOD:
        return ("EXPANSION", ["regime_spy_insufficient_bars"])
    sma_200 = sum(spy_closes[-_SMA_REGIME_PERIOD:]) / Decimal(str(_SMA_REGIME_PERIOD))
    last_close = spy_closes[-1]
    regime = "EXPANSION" if last_close >= sma_200 else "CONTRACTION"
    return (regime, [])


def compute_market_state(dataset: MarketDataset) -> MarketState:
    regime, regime_reason_codes = _regime_signal(dataset)
    features: dict[str, TickerFeatures] = {}
    reason_codes: list[str] = list(regime_reason_codes)

    for ticker, ticker_data in dataset.data.items():
        closes = [bar.close for bar in ticker_data.ohlcv]
        mom = _momentum_20d(closes, ticker)
        vol = _volatility_20d(closes, ticker)
        rsi, clamped = _rsi_14(closes, ticker)
        ewma_vol = _volatility_ewma(closes, ticker)
        scsi = _scsi_from_sentiment(ticker_data.news_sentiment)
        if clamped:
            reason_codes.append(f"rsi_clamped:{ticker}")
        features[ticker] = TickerFeatures(
            momentum_20d=mom,
            volatility_20d=vol,
            rsi_14=rsi,
            volatility_ewma=ewma_vol,
            scsi=scsi,
        )

    params_hash = hashlib.sha256(
        f"{dataset.params_hash}|market_state_engine_v1".encode()
    ).hexdigest()

    return MarketState(
        features=features,
        as_of_date=dataset.as_of_date,
        params_hash=params_hash,
        regime=regime,
        validation_status="valid",
        reason_codes=reason_codes,
    )
