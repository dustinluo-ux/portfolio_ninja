# Active Risk Register — portfolio_ninja

> Living risk register. Update when risks change status or new risks emerge.

---

## Current Risks

| risk_id | description | category | severity | status | mitigation plan | owner |
|---------|-------------|----------|----------|--------|-----------------|-------|
| R001 | Float precision in price/weight calculations causes incorrect portfolio allocations | data | high | mitigated | `decimal.Decimal` enforced throughout; `variance.sqrt()` used (no `float()`); CI lint gate blocks `float(` near monetary fields; 0 `float(` found in src/ | self |
| R002 | Cross-module contract drift — one module changes output schema without updating downstream contracts | logic | high | mitigated | Sealed node rule enforced; ADR gate hook in `.claude/settings.json`; all 12 contracts status=implemented and match implementation signatures | self |
| R003 | Silent fallback in data fetch masks missing data and produces stale signals | logic | high | mitigated | Fail-loud rule enforced; DataPlane raises DataUnavailableError / DataIntegrityError; no defaults in production path | self |
| R004 | Live mode execution adapter fires real orders during backtest or paper mode | logic | high | mitigated | Mode flag validated at orchestrator entry; ExecutionEngine receives adapter via injection (no internal factory branch); StubExecutionAdapter used in all MVP tests | self |
| R005 | Lineage fields missing from output objects enables undetectable staleness | data | medium | mitigated | All 11 pipeline domain objects carry: as_of_date, params_hash, validation_status, reason_codes; AuditMonitor validates all 9 required pipeline_hashes; integrator verified completeness | self |
| R006 | External data API rate limits or outages block pipeline in live mode | external | medium | mitigated | DataPlane adapter raises DataUnavailableError; orchestrator surfaces immediately; MVP uses StubDataAdapter with zero external calls; real adapter is future swap | self |
| R007 | StubDataAdapter produces non-deterministic data if RNG seed is not fixed, causing irreproducible test failures | data | high | mitigated | StubDataAdapter seeds RNG with seed=42 in __init__; smoke test asserts output hash identical across two calls with same inputs | self |
| R008 | Orchestrator silently skips a module if wiring is incorrect, producing an incomplete AuditRecord | logic | high | mitigated | Smoke test asserts every domain object in the canonical chain is non-null and valid; AuditMonitor.assemble_audit_record() raises AuditIncompleteError if any of the 9 required pipeline_hashes is missing or empty | self |

---

## Risk Categories

| Category | Definition |
|----------|------------|
| logic | Flawed reasoning, edge cases, hallucinations |
| data | Data corruption, precision loss, schema drift |
| external | API failures, dependency issues, MCP conflicts |
| security | Secrets exposure, injection, access control |

---

## Severity Levels

| Level | Criteria |
|-------|----------|
| high | Data loss, wrong trades, incorrect portfolio allocation, security breach |
| medium | Degraded signal quality, technical debt, workaround needed |
| low | Cosmetic, documentation, minor inconvenience |

---

## Status Lifecycle

| Status | Meaning | Action |
|--------|---------|--------|
| open | Risk present, mitigation not applied | Prioritize mitigation |
| mitigated | Control in place, risk reduced | Monitor for regression |
| closed | Risk no longer applicable | Archive with rationale |
