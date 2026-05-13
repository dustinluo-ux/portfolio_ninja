# Contract: Domain Objects

## Purpose
Document all shared typed domain objects and adapter interfaces that form the exclusively permitted cross-module handoff layer for portfolio_ninja.

## Status
implemented

## Notes
This is a pseudo-contract for the shared domain layer (`src/portfolio_ninja/domain/`). It is not a pipeline module and has no Inputs/Outputs tables. All 11 pipeline modules depend on this layer. No pipeline module may import from another pipeline module's source path — all cross-module handoffs use only types defined here.

---

## Domain Objects

All objects are dataclasses defined in `src/portfolio_ninja/domain/objects.py`.

### Non-Pipeline Value Objects

| Object | Fields | Notes |
|--------|--------|-------|
| `RunConfig` | `tickers: list[str]`, `run_mode: str`, `window_days: int` (default 730) | Orchestrator-level input; not a pipeline handoff object |
| `OHLCVBar` | `date: date`, `open: Decimal`, `high: Decimal`, `low: Decimal`, `close: Decimal`, `volume: int` | All price fields are `decimal.Decimal`; volume is `int` |
| `TickerData` | `ohlcv: list[OHLCVBar]`, `news_sentiment: Decimal`, `pe_ratio: Decimal` | Nested inside `MarketDataset.data` |
| `TickerFeatures` | `momentum_20d: Decimal`, `volatility_20d: Decimal`, `rsi_14: Decimal` | Nested inside `MarketState.features` |
| `Order` | `ticker: str`, `direction: str` ("buy"/"sell"), `quantity: Decimal`, `order_type: str` ("market") | No lineage fields; nested inside `ExecutionIntent.orders` |

### Pipeline Handoff Objects

All pipeline handoff objects carry the full lineage field set. Objects that participate in the canonical decision path must implement a `validate()` method that raises `ValueError` on invalid state.

#### Lineage Field Set (present on every pipeline handoff object)

| Field | Type | Description |
|-------|------|-------------|
| `as_of_date` | `date` | Business date this object represents (UTC date) |
| `params_hash` | `str` | SHA-256 hex digest of the inputs used to produce this object |
| `validation_status` | `str` | `"valid"` or `"invalid"` |
| `reason_codes` | `list[str]` | Non-empty when `validation_status == "invalid"` or warnings present |

**Exception:** `ExperimentParams` does not carry `as_of_date` (no temporal dimension); `AuditRecord` carries `completed_at: datetime` instead of `as_of_date`. Both carry `validation_status` and `reason_codes`.

**Exception:** `MarketDataset` additionally carries `source_data_version: str` (non-empty string identifying the data adapter and version).

| Object | Key Fields | Lineage Fields |
|--------|-----------|----------------|
| `Universe` | `tickers: list[str]`, `run_mode: str`, `window_days: int` | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `MarketDataset` | `data: dict[str, TickerData]`, `source_data_version: str` | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `MarketState` | `features: dict[str, TickerFeatures]` | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `ExperimentParams` | `scoring_model_id: str`, `top_n: int`, `rebalance_freq: str` | `params_hash`, `validation_status`, `reason_codes` |
| `ScoreSet` | `scores: dict[str, Decimal]`, `model_id: str` | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `RankedUniverse` | `ranked: list[tuple[str, Decimal]]` | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `TargetPortfolio` | `weights: dict[str, Decimal]` (MUST sum to `Decimal("1.0")`) | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `RiskDecision` | `approved: bool`, `weights: dict[str, Decimal]`, `adjustments: list[str]` | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `ExecutionIntent` | `orders: list[Order]`, `adapter_id: str`, `run_mode: str` | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `EvaluationReport` | `cycle_id: str`, `pnl: Decimal`, `sharpe: Decimal`, `max_drawdown: Decimal` | `as_of_date`, `params_hash`, `validation_status`, `reason_codes` |
| `AuditRecord` | `cycle_id: str`, `run_mode: str`, `tickers: list[str]`, `pipeline_hashes: dict[str, str]`, `completed_at: datetime` | `validation_status`, `reason_codes` |

---

## Adapter Interfaces

Defined in `src/portfolio_ninja/domain/adapters.py`.

| Interface | Method | Signature | Notes |
|-----------|--------|-----------|-------|
| `DataAdapter` (ABC) | `fetch` | `fetch(universe: Universe, window_days: int) -> MarketDataset` | Raises on any fetch failure; no silent fallback |
| `ExecutionAdapter` (ABC) | `submit` | `submit(intent: ExecutionIntent) -> None` | Raises on any submission failure; no silent fallback |

### Stub Implementations (`src/portfolio_ninja/domain/stubs.py`)

| Stub | Behavior |
|------|---------|
| `StubDataAdapter` | Deterministic dummy OHLCV/news/fundamentals; seeded RNG (`seed=42`); same inputs always produce same output; implements `DataAdapter` |
| `StubExecutionAdapter` | Logs `ExecutionIntent` via `logging` module; returns immediately; no broker call; implements `ExecutionAdapter` |

---

## Dependencies
- None — this is the base layer; no module dependency

## Invariants
- All monetary, weight, and price fields use `decimal.Decimal`; never `float`
- Every pipeline handoff object (Universe, MarketDataset, MarketState, ExperimentParams, ScoreSet, RankedUniverse, TargetPortfolio, RiskDecision, ExecutionIntent, EvaluationReport, AuditRecord) carries `validation_status: str` and `reason_codes: list[str]`
- Every pipeline handoff object except ExperimentParams and AuditRecord carries `as_of_date: date`
- Every pipeline handoff object carries `params_hash: str` (SHA-256 hex of deterministic inputs)
- `AuditRecord` carries `completed_at: datetime` (UTC) instead of `as_of_date`
- `MarketDataset` additionally carries `source_data_version: str` (non-empty)
- `validate()` raises `ValueError` on invalid state for every pipeline object
- No pipeline module imports from another pipeline module's source path
- All cross-module handoffs use only types from this domain layer
- `TargetPortfolio.weights` values must sum exactly to `Decimal("1.0")`
- `Order.direction` must be `"buy"` or `"sell"`
- `Order.order_type` must be `"market"`
- `OHLCVBar.high >= OHLCVBar.low` always
- `OHLCVBar.volume >= 0` always
- `TickerFeatures.rsi_14` is in range `[Decimal("0"), Decimal("100")]`
- `StubDataAdapter` uses seeded RNG (seed=42); output is deterministic for identical inputs
- `Universe.run_mode` is one of `{"backtest", "paper", "live"}`
- `Universe.window_days > 0`

## Failure Modes
| Failure | Probability | Impact | Mitigation |
|---------|-------------|--------|------------|
| Field type drift (float introduced) | M | H | Lint gate blocks `float(` near monetary fields; all tests assert `Decimal` |
| Missing lineage field on pipeline object | L | H | `validate()` raises `ValueError` on construction if required lineage fields are empty or absent |
| StubDataAdapter non-determinism | L | H | Seed fixed to 42 globally; smoke test asserts identical output hash across two calls with same inputs |
| Generic dict used instead of domain object | M | H | Sealed node architecture; code-reviewer rejects any `dict` at module boundaries |
| `TargetPortfolio.weights` sum != 1.0 | M | H | `validate()` raises `ValueError`; `RiskDecision.validate()` double-checks |

## Tests Required
- [ ] `test_domain_universe_validate_valid_state_passes`
- [ ] `test_domain_universe_validate_empty_tickers_raises_value_error`
- [ ] `test_domain_universe_validate_invalid_run_mode_raises_value_error`
- [ ] `test_domain_market_dataset_validate_valid_state_passes`
- [ ] `test_domain_market_dataset_validate_empty_source_data_version_raises_value_error`
- [ ] `test_domain_market_state_validate_valid_state_passes`
- [ ] `test_domain_market_state_validate_rsi_out_of_range_raises_value_error`
- [ ] `test_domain_experiment_params_validate_valid_state_passes`
- [ ] `test_domain_experiment_params_validate_top_n_zero_raises_value_error`
- [ ] `test_domain_score_set_validate_valid_state_passes`
- [ ] `test_domain_score_set_validate_score_out_of_range_raises_value_error`
- [ ] `test_domain_ranked_universe_validate_valid_state_passes`
- [ ] `test_domain_target_portfolio_validate_weights_sum_to_one_passes`
- [ ] `test_domain_target_portfolio_validate_weights_not_sum_to_one_raises_value_error`
- [ ] `test_domain_risk_decision_validate_valid_state_passes`
- [ ] `test_domain_execution_intent_validate_valid_state_passes`
- [ ] `test_domain_evaluation_report_validate_valid_state_passes`
- [ ] `test_domain_audit_record_validate_valid_state_passes`
- [ ] `test_domain_audit_record_validate_missing_pipeline_hash_raises_value_error`
- [ ] `test_domain_stub_data_adapter_is_deterministic_for_same_inputs`
- [ ] `test_domain_ohlcv_bar_high_gte_low_invariant`
- [ ] `test_domain_order_direction_must_be_buy_or_sell`

## Acceptance Criteria
- [ ] All 16 domain object types defined as dataclasses in `src/portfolio_ninja/domain/objects.py`
- [ ] `DataAdapter` and `ExecutionAdapter` ABCs defined in `src/portfolio_ninja/domain/adapters.py`
- [ ] `StubDataAdapter` and `StubExecutionAdapter` defined in `src/portfolio_ninja/domain/stubs.py`
- [ ] `StubDataAdapter` produces identical output for identical inputs (seed=42 verified by test)
- [ ] All monetary/weight/price fields are `decimal.Decimal`; no `float` in domain layer
- [ ] `validate()` method exists on every pipeline handoff object and raises `ValueError` on invalid state
- [ ] All lineage fields present on every pipeline handoff object

## Upstream Providers
- None (base layer)

## Downstream Consumers
- All 11 pipeline modules: UniverseGateway, DataPlane, MarketStateEngine, ExperimentEngine, ScoringEngine, ScoreArbitrationEngine, PortfolioConstructionEngine, RiskEngine, ExecutionEngine, EvaluationEngine, AuditMonitor
