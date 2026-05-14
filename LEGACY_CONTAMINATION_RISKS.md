# LEGACY_CONTAMINATION_RISKS.md
# ai_supply_chain_trading — Contamination Risk Inventory
> Generated: 2026-05-13 | Read-only mine. New architecture contracts are frozen.

Every risk below is evidence-backed from code. No risk is inferred from comments alone.

---

## Risk Classification

| Severity | Meaning |
|----------|---------|
| CRITICAL | Silent wrong answer in production; would bypass type safety in new architecture |
| HIGH | Compilation fails or wrong result if ported unchanged |
| MEDIUM | Degrades correctness or observability; won't cause immediate failure |
| LOW | Code smell; acceptable in isolation but bad pattern |

---

## CR-001 — Generic Dict Aliases Contaminate Type Safety

**File:** `src/core/types.py`  
**Severity:** CRITICAL  
**Category:** Hidden coupling / generic dicts

**Evidence:**
```python
DataContext = dict[str, Any]
Context = dict[str, Any]   # semantically identical to DataContext — dead alias
```

**Risk:** Any code that accepts `DataContext` as a parameter accepts any dict, silently. If ported into a module that expects a typed domain object, it erases the type contract. The new architecture rule "No generic dicts across module boundaries" is directly violated.

**Contamination path:** `DataContext` is passed between several modules. If a builder ports any of these call sites, the dict alias travels with it.

**Mitigation:** Do not port `types.py`. Rewrite all cross-module handoffs as typed dataclasses per the domain objects spec.

---

## CR-002 — Float Weights in Intent Cross-Module Handoff

**File:** `src/core/intent.py`  
**Severity:** CRITICAL  
**Category:** Float contamination in monetary/weight fields

**Evidence:**
```python
@dataclass
class Intent:
    weights: dict[str, float]   # ← float, not Decimal
    # ...
```

**Risk:** `Intent.weights` is the cross-module handoff between PortfolioConstructionEngine and ExecutionEngine. If ported, float rounding errors accumulate in execution quantities. The Decimal rule is violated at the handoff boundary.

**Contamination path:** `Intent` is consumed by `planner.py` (ExecutionEngine candidate). Planner internally uses Decimal, but receives float weights — the contamination lives at the interface.

**Mitigation:** Do not port `Intent`. New `ExecutionIntent` domain object already specifies `weights: dict[str, Decimal]`.

---

## CR-003 — Float Return Type in Base Data Provider Interface

**File:** `src/data/base_provider.py`  
**Severity:** HIGH  
**Category:** Float contamination at API boundary

**Evidence:**
```python
class DataProvider(ABC):
    @abstractmethod
    def get_current_price(self, ticker: str) -> float:
        ...
```

**Risk:** All concrete providers that implement this interface return `float`. If ported, any consumer that uses `get_current_price()` receives a float price — violating Decimal rule. The abstract contract enforces the contamination.

**Contamination path:** `CSVProvider`, `IBKRLiveProvider`, and `ResilienceLayer` all implement this interface. Porting any one of them without changing the interface propagates float.

**Mitigation:** Do not port `base_provider.py`. New `DataAdapter` interface specifies `fetch() -> MarketDataset` with Decimal OHLCV.

---

## CR-004 — Silent Fallback to CSV on Any Exception (Provider Factory)

**File:** `src/data/provider_factory.py`  
**Severity:** HIGH  
**Category:** Silent fallback / bare except

**Evidence:**
```python
try:
    return IBKRLiveProvider(config)
except Exception:
    return CSVProvider(config)   # silent, no log
```

**Risk:** Live data provider failure silently falls back to stale CSV data. The caller has no way to know it is not receiving live data. In a trading system, this is a production correctness hazard.

**Contamination path:** If the resilience pattern is ported but the silent-fallback behavior is preserved, the new DataPlane will silently degrade without surfacing the failure.

**Mitigation:** Port the resilience_layer structure (explicit chain with logged fallbacks), not the factory. Ensure each fallback step raises `IncompleteDataError` or logs a `WARN` with the fallback source name.

---

## CR-005 — Silent Skip in CSV Provider (Print, Not Raise)

**File:** `src/data/csv_provider.py`  
**Severity:** HIGH  
**Category:** Silent fallback / mixed print/raise discipline

**Evidence:**
```python
except FileNotFoundError:
    print(f"CSV file not found: {path}")   # print, not raise; not logged
    return {}
```

**Risk:** Missing data file silently returns an empty dict. Downstream modules receive no prices and may silently produce zero weights or crash with a KeyError rather than a clean error.

**Contamination path:** If `csv_provider.py` is ported as a stub, the print-and-return-empty pattern travels with it.

**Mitigation:** Rewrite from scratch. New stub adapter uses `raise FileNotFoundError` or returns a `DataQualityReport` with `is_complete=False`.

---

## CR-006 — Dual Bare Excepts in Resilience Layer Fallback Chain

**File:** `src/data/resilience_layer.py`  
**Severity:** HIGH  
**Category:** Bare except / swallowed exceptions

**Evidence:**
```python
def _try_marketaux(self, ticker):
    try:
        ...
    except Exception:   # swallows all errors — rate limit, auth failure, parse error
        return None

def _try_yfinance(self, ticker):
    try:
        ...
    except Exception:   # same
        return None
```

**Risk:** Any exception (including `KeyboardInterrupt` in Python < 3.11, auth failures, network timeouts, malformed JSON) is swallowed silently. The fallback chain always reports a result, even if all providers failed and returned `None`.

**Contamination pattern:** The overall structure (CSV → Marketaux → YFinance) is reusable. The bare excepts are not.

**Mitigation:** Port the fallback chain structure. Replace bare excepts with typed catches (`requests.exceptions.Timeout`, `requests.exceptions.HTTPError`, etc.) and log the specific failure before falling through.

---

## CR-007 — Hardcoded Absolute Paths (Machine-Specific)

**Files:**
- `config/model_config.yaml` — `model_path: C:\Users\User\...` (wrong username — another machine)
- `src/data/news_fetcher_factory.py` — hardcoded `DATA_DIR` fallback path
- `scripts/update_universe.py` — hardcoded Python executable path
- `scripts/scouting_module.py` — hardcoded `DATA_DIR` fallback

**Severity:** HIGH  
**Category:** Hardcoded paths / portability

**Evidence:**
```yaml
# config/model_config.yaml
model_path: "C:\\Users\\User\\...\\catboost_20260308_103404.pkl"   # ← wrong username
```

**Risk:** Code that references these paths will fail silently or raise `FileNotFoundError` on any machine other than the original developer's. Porting any of these files without purging the hardcoded paths introduces machine-specific failures.

**Contamination path:** If `model_factory.py` or any config reader is ported, it may reference `model_config.yaml` and attempt to load the stale model path.

**Mitigation:** Replace all path references with `pathlib.Path(os.environ["PORTFOLIO_NINJA_DATA_DIR"])` or equivalent. Never hardcode drive letters.

---

## CR-008 — Config Drift Across 5 Parameters (No SSOT)

**Files:** `config/technical_master_score.yaml`, `config/strategy_params.yaml`, `config/model_config.yaml`, `config/trading_config.yaml`, `config/layered_signal_config.yaml`  
**Severity:** HIGH  
**Category:** Config drift / duplicated logic

**Evidence:**

| Parameter | Value A | Source A | Value B | Source B | Magnitude |
|-----------|---------|----------|---------|----------|-----------|
| `news_weight` | 0.20 | `technical_master_score.yaml` | 0.30 | `strategy_params.yaml` optimizer | 50% difference |
| `ml_blend_weight` | 0.30 | `model_config.yaml` | 0.10 | `strategy_params.yaml` optimizer | 3× difference |
| `three_layer_engine_weight` | 0.30 | `strategy_params.yaml` | 0.40 | `layered_signal_config.yaml` | 33% difference |
| `trend_weight` | 0.40 | `technical_master_score.yaml` | 0.50 | `strategy_params.yaml` optimizer | 25% difference |
| `max_position` | 0.10 (Track D) | `model_config.yaml` | 0.40 | `trading_config.yaml` | 4× difference |

**Risk:** Porting any config file without understanding which value is authoritative will silently produce wrong scoring or position sizing. The `three_layer_engine_weight` drift is particularly dangerous — the entire layered engine is disabled (`use_layered_engine: false`) but the config is not cleaned up, creating a false impression that the system uses it.

**Mitigation:** Do not port any config file directly. Extract only the numeric constants needed by the new module. Declare a single SSOT in `portfolio_ninja/config/`. For the `max_position` drift, note that Track D (0.10) is the intended production value; 0.40 in `trading_config.yaml` is a holdover from a different risk tolerance.

---

## CR-009 — Float TES Output (Decimal Computed Internally, Cast at Return)

**File:** `lib/shared_core/tes_scorer.py`  
**Severity:** HIGH  
**Category:** Float contamination at module output boundary

**Evidence:**
```python
def compute_tes(revenue_ratio, cagr, patent_density=0.10):
    result = Decimal(str(revenue_ratio)) * (1 + Decimal(str(cagr))) * Decimal(str(patent_density))
    return float(result)   # ← casts back to float at return boundary
```

**Risk:** The computation is Decimal-clean internally. The return type is `float`. Any module that calls `compute_tes()` receives a float score. If ported as-is into ScoringEngine, the `ScoreSet.score` field (which must be `Decimal`) would receive a float.

**Contamination path:** `TES score → ScoringEngine.score_ticker() → ScoreSet.score`. One float at the boundary poisons the whole chain.

**Mitigation:** Rewrite to return `Decimal`. Remove the `float(result)` cast. Also fix `patent_density=0.10` stub (see CR-015).

---

## CR-010 — Float Throughout All Pod Weight Computations

**Files:** `pods/pod_core.py`, `pods/pod_ballast.py`, `pods/meta_allocator.py`, `pods/aggregator.py`  
**Severity:** HIGH  
**Category:** Float contamination in weight fields

**Evidence (pod_core.py):**
```python
weights = hrp_weights  # numpy array → float dict
w_tilted = {t: weights[t] * (score / mean_score) for t in tickers}  # float arithmetic
```

**Evidence (aggregator.py):**
```python
def apply_gross_caps(weights: dict[str, float]) -> dict[str, float]:
    ...
```

**Risk:** All pod weight computations use float arithmetic with numpy. The final portfolio weights are float dicts. If any of these functions are ported, they produce float weights that violate the `TargetPortfolio.weights: dict[str, Decimal]` contract.

**Contamination path:** Pod outputs → `TargetPortfolio` → `RiskEngine` → `ExecutionEngine`. Float at the pod output level propagates through the entire downstream chain.

**Mitigation:** The HRP algorithm and alpha tilt formula are reusable ideas (Class B). Rewrite as Decimal arithmetic using `quantize()` for normalization. Do not port the float pod implementations directly.

---

## CR-011 — Silent HRP Failure Fallback to Equal Weight

**File:** `pods/pod_core.py`  
**Severity:** MEDIUM  
**Category:** Silent fallback

**Evidence:**
```python
try:
    hrp_weights = self._compute_hrp(returns)
except Exception:
    hrp_weights = {t: 1.0 / len(tickers) for t in tickers}  # silent equal weight fallback
```

**Risk:** HRP computation failure (singular covariance matrix, insufficient data, numpy error) silently produces equal weights. The caller receives a valid-looking result with no indication that HRP failed. In a live system, this could mean a degraded portfolio is executed without any alert.

**Mitigation:** Remove the bare except. Let HRP errors propagate. If equal-weight fallback is desired, log it explicitly as a `WARN` with the failure reason and return a `RiskDecision.approved=False` with `reason_codes=["hrp_fallback"]`.

---

## CR-012 — Three Bare Excepts Swallowing All Errors in Structural Breakdown

**File:** `src/monitoring/structural_breakdown.py`  
**Severity:** MEDIUM  
**Category:** Bare except / swallowed exceptions

**Evidence:**
```python
def assess_ic_decay(self):
    try:
        ...
    except Exception:
        pass   # IC decay assessment silently returns None

def assess_residual(self):
    try:
        ...
    except Exception:
        pass

def assess_beta(self):
    try:
        ...
    except Exception:
        pass
```

**Risk:** All three sub-assessments silently return `None` on any failure. If `structural_breakdown.py` is ported into the AuditMonitor, it will produce incomplete audit records that appear valid.

**Mitigation:** This file maps to AuditMonitor (Class B — ideas only). The IC decay and beta decay assessment concepts are useful; the implementation is not. Rewrite from scratch with explicit error returns.

---

## CR-013 — Hardcoded Account Number in Config

**File:** `config/trading_config.yaml`  
**Severity:** MEDIUM  
**Category:** Hardcoded secret / credential in config

**Evidence:**
```yaml
ibkr:
  paper_account: "DUM879076"
  live_account: "..."   # likely present but not confirmed
```

**Risk:** IBKR paper account identifier is committed to source control. While paper accounts have no monetary risk, this establishes a bad pattern. If the live account number follows the same pattern, it will be committed.

**Mitigation:** Do not port `trading_config.yaml`. Replace with environment variable references: `IBKR_PAPER_ACCOUNT`, `IBKR_LIVE_ACCOUNT`.

---

## CR-014 — TES Patent Density is a Constant Stub (Always 0.10)

**File:** `lib/shared_core/tes_scorer.py`  
**Severity:** MEDIUM  
**Category:** Stub masquerading as real signal

**Evidence:**
```python
def compute_tes(revenue_ratio, cagr, patent_density=0.10):
    # patent_density is always 0.10 — never varies per company
    ...
```

**Risk:** The TES formula weights `patent_density` as a meaningful differentiator across companies. Using a constant means all companies receive the same patent factor, making TES effectively `revenue_ratio × (1+cagr) × 0.10` — a scaled revenue-growth product. This is not wrong for an MVP stub, but is a contamination risk if ported without documentation: a future developer may assume `patent_density` varies.

**Mitigation:** Port the formula. Document the stub explicitly: `patent_density: Decimal = Decimal("0.10")  # stub — no patent data source connected`. Add a TODO in the contract, not in src/.

---

## CR-015 — Mutable Global State: Live Timestamps and Source Paths in Config

**File:** `config/strategy_params.yaml`  
**Severity:** LOW  
**Category:** Mutable global state in config

**Evidence:**
```yaml
universe:
  promoted_at: "2026-03-15T09:23:11"  # runtime state committed to config
  source: "/mnt/data/..."              # machine-specific path in config
```

**Risk:** Production runtime state (timestamps, resolved paths) is committed back into the config file. If ported, the config appears to have a fixed universe promotion date and a hardcoded source path, both of which are wrong in a new environment.

**Mitigation:** Do not read `promoted_at` or `source` from config. These are runtime outputs that belong in the database/audit log, not config. The new UniverseGateway receives its universe from the `Universe` domain object, which carries `as_of_date` as a proper field.

---

## CR-016 — `_guess_ticker()` 2-Entry Hardcoded Map in Auditor

**File:** `auditor/orchestrator.py`  
**Severity:** LOW  
**Category:** Dead / stub logic masquerading as real functionality

**Evidence:**
```python
def _guess_ticker(self, company_name: str) -> str:
    mapping = {"ON Semiconductor": "ON", "Apple": "AAPL"}
    return mapping.get(company_name, company_name[:4].upper())
```

**Risk:** Any audit that calls `_guess_ticker()` for a company not in the 2-entry map silently returns the first 4 characters of the name as a ticker. For "NVIDIA" → "NVID", for "Microsoft" → "MICR". These are wrong tickers that will silently pass downstream validation if not caught.

**Contamination path:** If `orchestrator.py` is ported into AuditMonitor, `_guess_ticker()` travels with it and silently produces wrong tickers for 99% of companies.

**Mitigation:** Delete this function. New AuditMonitor receives `ticker` as an explicit field on `Universe`. There is no guessing.

---

## CR-017 — Backtest / Live Divergence: Regime Controller Reads Different Data Sources

**File:** `src/execution/regime_controller.py`  
**Severity:** MEDIUM  
**Category:** Backtest/live divergence

**Evidence:**
```python
# In paper/live mode:
spy_price = self._fetch_live_spy()   # yfinance live call

# In backtest mode (implied by strategy_params.yaml `mode: paper`):
spy_price = self._read_csv_spy()     # CSV file — potentially stale
```

**Risk:** The regime signal (SPY/200-SMA binary) uses different data sources in paper vs. live modes. A backtest that shows a regime transition may not match a paper run that reads from a stale CSV file. The regime binary is a critical gating signal for position sizing (`max_longs: 3 vs 5`, `size_multiplier: 0.6 vs 1.0`).

**Mitigation:** The regime concept is valuable (Class B). The data source switching logic is contaminated. New MarketStateEngine must use a single data source abstracted via `DataAdapter`, regardless of run mode.

---

## CR-018 — `ibkr_nav.py` Never Raises (Returns `None` on Any Failure)

**File:** `src/execution/ibkr_nav.py`  
**Severity:** MEDIUM  
**Category:** Silent fallback / never raises

**Evidence:**
```python
def fetch_nav(self) -> float | None:
    try:
        ...
        return float(account_summary["NetLiquidation"])
    except Exception:
        return None   # caller must check for None; no log
```

**Risk:** NAV fetch failure returns `None` silently. If the caller does not explicitly check `if nav is None`, it proceeds with `None` NAV — which will cause a `TypeError` downstream in position sizing. The pattern is: silent `None` → unguarded arithmetic → crash far from the source.

**Contamination path:** If `ibkr_nav.py` is ported, the `None` return on failure travels with it. The new ExecutionEngine's stub adapter must never return `None` — it must raise `ExecutionAdapterError` with a specific message.

**Mitigation:** Do not port. New `ExecutionAdapter.submit()` raises on failure. NAV is not a required input to the new ExecutionEngine (it uses weights, not NAV, to size positions in the stub).

---

## Summary Table

| Risk ID | File | Severity | Category | Action |
|---------|------|----------|----------|--------|
| CR-001 | `src/core/types.py` | CRITICAL | Generic dict aliases | Delete entirely |
| CR-002 | `src/core/intent.py` | CRITICAL | Float weights at handoff | Do not port; use `ExecutionIntent` |
| CR-003 | `src/data/base_provider.py` | HIGH | Float return at boundary | Do not port; use `DataAdapter` |
| CR-004 | `src/data/provider_factory.py` | HIGH | Silent fallback to CSV | Port structure only; fix bare except |
| CR-005 | `src/data/csv_provider.py` | HIGH | Print-not-raise silent skip | Rewrite from scratch |
| CR-006 | `src/data/resilience_layer.py` | HIGH | Dual bare excepts | Port chain structure; fix excepts |
| CR-007 | Multiple (4 files) | HIGH | Hardcoded absolute paths | Never port; use env vars |
| CR-008 | Multiple configs (5 files) | HIGH | Config drift — no SSOT | Extract constants only; no file port |
| CR-009 | `lib/shared_core/tes_scorer.py` | HIGH | Float return from Decimal | Rewrite to return Decimal |
| CR-010 | `pods/*.py` (4 files) | HIGH | Float pod weights | Rewrite as Decimal arithmetic |
| CR-011 | `pods/pod_core.py` | MEDIUM | Silent HRP fallback | Fix to explicit error + log |
| CR-012 | `src/monitoring/structural_breakdown.py` | MEDIUM | 3× bare except pass | Rewrite from scratch |
| CR-013 | `config/trading_config.yaml` | MEDIUM | Hardcoded account number | Never port; use env vars |
| CR-014 | `lib/shared_core/tes_scorer.py` | MEDIUM | Constant patent stub | Port formula + document stub |
| CR-015 | `config/strategy_params.yaml` | LOW | Runtime state in config | Never read promoted_at/source |
| CR-016 | `auditor/orchestrator.py` | LOW | 2-entry hardcoded ticker map | Delete function |
| CR-017 | `src/execution/regime_controller.py` | MEDIUM | Backtest/live data divergence | Port concept; fix data source abstraction |
| CR-018 | `src/execution/ibkr_nav.py` | MEDIUM | Never-raises None return | Do not port; stub raises on failure |
