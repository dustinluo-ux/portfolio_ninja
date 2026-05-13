from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass
class RunConfig:
    tickers: list[str]
    run_mode: str  # "backtest" | "paper" | "live"
    window_days: int = 730


@dataclass
class OHLCVBar:
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def validate(self) -> None:
        if self.high < self.low:
            raise ValueError(f"OHLCVBar.high ({self.high}) < low ({self.low})")
        if self.volume < 0:
            raise ValueError(f"OHLCVBar.volume must be >= 0, got {self.volume}")


@dataclass
class TickerData:
    ohlcv: list[OHLCVBar]
    news_sentiment: Decimal
    pe_ratio: Decimal


@dataclass
class TickerFeatures:
    momentum_20d: Decimal
    volatility_20d: Decimal
    rsi_14: Decimal

    def validate(self) -> None:
        if not (Decimal("0") <= self.rsi_14 <= Decimal("100")):
            raise ValueError(f"rsi_14 must be in [0, 100], got {self.rsi_14}")


@dataclass
class Order:
    ticker: str
    direction: str  # "buy" | "sell"
    quantity: Decimal
    order_type: str = "market"

    def validate(self) -> None:
        if self.direction not in ("buy", "sell"):
            raise ValueError(f"Order.direction must be 'buy' or 'sell', got {self.direction!r}")
        if self.order_type != "market":
            raise ValueError(f"Order.order_type must be 'market', got {self.order_type!r}")
        if self.quantity <= Decimal("0"):
            raise ValueError(f"Order.quantity must be > 0, got {self.quantity}")


# --- Pipeline handoff objects (all carry lineage fields) ---

@dataclass
class Universe:
    tickers: list[str]
    run_mode: str
    window_days: int
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.tickers:
            raise ValueError("Universe.tickers must not be empty")
        if self.run_mode not in ("backtest", "paper", "live"):
            raise ValueError(f"Universe.run_mode must be backtest/paper/live, got {self.run_mode!r}")
        if self.window_days <= 0:
            raise ValueError(f"Universe.window_days must be > 0, got {self.window_days}")
        if not self.params_hash:
            raise ValueError("Universe.params_hash must not be empty")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError(f"validation_status must be 'valid' or 'invalid', got {self.validation_status!r}")


@dataclass
class MarketDataset:
    data: dict[str, TickerData]
    source_data_version: str
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.data:
            raise ValueError("MarketDataset.data must not be empty")
        if not self.source_data_version:
            raise ValueError("MarketDataset.source_data_version must not be empty")
        if not self.params_hash:
            raise ValueError("MarketDataset.params_hash must not be empty")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


@dataclass
class MarketState:
    features: dict[str, TickerFeatures]
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.features:
            raise ValueError("MarketState.features must not be empty")
        if not self.params_hash:
            raise ValueError("MarketState.params_hash must not be empty")
        for ticker, f in self.features.items():
            f.validate()
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


@dataclass
class ExperimentParams:
    scoring_model_id: str
    top_n: int
    rebalance_freq: str  # "daily" | "weekly" | "monthly"
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.scoring_model_id:
            raise ValueError("ExperimentParams.scoring_model_id must not be empty")
        if self.top_n < 1:
            raise ValueError(f"ExperimentParams.top_n must be >= 1, got {self.top_n}")
        if self.rebalance_freq not in ("daily", "weekly", "monthly"):
            raise ValueError(f"rebalance_freq must be daily/weekly/monthly, got {self.rebalance_freq!r}")
        if not self.params_hash:
            raise ValueError("ExperimentParams.params_hash must not be empty")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


@dataclass
class ScoreSet:
    scores: dict[str, Decimal]
    model_id: str
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.scores:
            raise ValueError("ScoreSet.scores must not be empty")
        if not self.model_id:
            raise ValueError("ScoreSet.model_id must not be empty")
        if not self.params_hash:
            raise ValueError("ScoreSet.params_hash must not be empty")
        for ticker, s in self.scores.items():
            if not (Decimal("0") <= s <= Decimal("1")):
                raise ValueError(f"Score for {ticker} must be in [0, 1], got {s}")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


@dataclass
class RankedUniverse:
    ranked: list[tuple[str, Decimal]]
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.ranked:
            raise ValueError("RankedUniverse.ranked must not be empty")
        if not self.params_hash:
            raise ValueError("RankedUniverse.params_hash must not be empty")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


@dataclass
class TargetPortfolio:
    weights: dict[str, Decimal]
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.weights:
            raise ValueError("TargetPortfolio.weights must not be empty")
        if not self.params_hash:
            raise ValueError("TargetPortfolio.params_hash must not be empty")
        total = sum(self.weights.values())
        if total != Decimal("1.0"):
            raise ValueError(f"TargetPortfolio.weights must sum to 1.0, got {total}")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


@dataclass
class RiskDecision:
    approved: bool
    weights: dict[str, Decimal]
    adjustments: list[str]
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.params_hash:
            raise ValueError("RiskDecision.params_hash must not be empty")
        if self.weights:
            total = sum(self.weights.values())
            if total != Decimal("1.0"):
                raise ValueError(f"RiskDecision.weights must sum to 1.0, got {total}")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


@dataclass
class ExecutionIntent:
    orders: list[Order]
    adapter_id: str
    run_mode: str
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.adapter_id:
            raise ValueError("ExecutionIntent.adapter_id must not be empty")
        if self.run_mode not in ("backtest", "paper", "live"):
            raise ValueError(f"ExecutionIntent.run_mode must be backtest/paper/live, got {self.run_mode!r}")
        if not self.params_hash:
            raise ValueError("ExecutionIntent.params_hash must not be empty")
        for order in self.orders:
            order.validate()
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


@dataclass
class EvaluationReport:
    cycle_id: str
    pnl: Decimal
    sharpe: Decimal
    max_drawdown: Decimal
    as_of_date: date
    params_hash: str
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.cycle_id:
            raise ValueError("EvaluationReport.cycle_id must not be empty")
        if not self.params_hash:
            raise ValueError("EvaluationReport.params_hash must not be empty")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")


_REQUIRED_PIPELINE_HASH_KEYS: frozenset[str] = frozenset({
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


@dataclass
class AuditRecord:
    cycle_id: str
    run_mode: str
    tickers: list[str]
    pipeline_hashes: dict[str, str]
    completed_at: datetime
    validation_status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.cycle_id:
            raise ValueError("AuditRecord.cycle_id must not be empty")
        if self.run_mode not in ("backtest", "paper", "live"):
            raise ValueError(f"AuditRecord.run_mode must be backtest/paper/live, got {self.run_mode!r}")
        missing = _REQUIRED_PIPELINE_HASH_KEYS - set(self.pipeline_hashes.keys())
        if missing:
            from .exceptions import AuditIncompleteError
            raise AuditIncompleteError(f"AuditRecord.pipeline_hashes missing keys: {missing}")
        empty = {k for k, v in self.pipeline_hashes.items() if not v}
        if empty:
            from .exceptions import AuditIncompleteError
            raise AuditIncompleteError(f"AuditRecord.pipeline_hashes has empty values for keys: {empty}")
        if self.validation_status not in ("valid", "invalid"):
            raise ValueError("validation_status must be 'valid' or 'invalid'")
