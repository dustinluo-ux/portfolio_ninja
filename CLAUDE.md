# portfolio_ninja

## Role

You are the implementation agent for **portfolio_ninja**.
Manufactured via factory `/manufacture` (HEAVY kit).

## Rules

Load from `.claude/rules/` as relevant:
- `architecture.md` — scaffold, ADR conventions, API design
- `testing.md` — coverage gates, root cause discipline
- `windows-maintenance.md` — atomic writes, path hygiene

## Pipeline

This project uses the **HEAVY kit**:
- Agents: architect, contract-writer, risk-checker, builder, spec-reviewer, code-reviewer, reviewer, integrator
- Managed Builder available for cloud-based module builds (see `scripts/managed_builder.py`)
- ADR gate enforced — `git commit` blocked if `src/` has Python files and `docs/adr/` has no decisions
- Risk register required before any plan is approved

## Session Loop

For new features or bug fixes within this project, follow this sequence:

1. **DEFINE** — Clarify requirements. Escalate class-B/C/D questions (see `docs/checklists/QUESTION_CLASSIFIER.md`).
2. **PLAN** — Architect decomposes into modules. Contract-writer writes contracts. User approves before build.
3. **RISK** — Risk-checker validates architecture, contracts, risk register, and SPOF coverage. Block until resolved.
4. **BUILD** — Builder implements per approved contract. One module at a time, sequential.
5. **VERIFY** — Reviewer runs spec + code review. Integrator sweeps end-to-end.
6. **DOCUMENT** — Update `docs/ARCHITECTURE.md` if modules changed. Log decisions in `docs/adr/`. Update `STATE_HANDOFF.md` and `STORY.md`.

Before closing a session, output:
- What is incomplete or deferred
- Any fragile areas flagged during build
- Exact next step

## Agents

Pipeline agents are at `.claude/agents/`. Available in this project:
- `architect` — module decomposition + execution graph
- `contract-writer` — module contracts
- `risk-checker` — risk register validation + SPOF coverage
- `builder` — implementation per module
- `spec-reviewer` — contract compliance review
- `code-reviewer` — code quality review
- `reviewer` — two-stage review orchestrator (spec + code)
- `integrator` — end-to-end sweep + completion gate

Global agents (always available): `researcher`, `compressor`

## Key Files

| File | Purpose |
|------|---------|
| `STATE_HANDOFF.md` | Session continuity — read first on resume |
| `STORY.md` | Append-only audit trail |
| `ACTIVE_RISK_REGISTER.md` | Live risks |
| `docs/ARCHITECTURE.md` | Module map, data flow, known limitations |
| `docs/adr/` | Architectural decision records (MADR format) |
| `docs/contracts/` | Module contracts |
| `docs/contracts/CONTRACT_INDEX.md` | Contract status index |
| `docs/checklists/COMPLETION_GATE.md` | Completion criteria — must pass before declaring done |

## Hard Limits

1. **Contract-first** — No builder runs without an approved contract in `docs/contracts/`
2. **Decimal, never float** — All monetary/price calculations use `decimal.Decimal`
3. **Risk register before plan** — No plan proceeds without a risk register; one SPOF per milestone
4. **Secrets in `.env` only** — Never hardcoded, never committed
5. **Atomic writes** — `.tmp` → validate non-empty → `os.replace()` to target
6. **Kill switch** — If `BUDGET_USD` is set, halt before any tool use that would breach it
7. **Completion gate required** — Never report "complete," "done," or "all fixes applied" without reviewer PASS + integrator PASS + `docs/checklists/COMPLETION_GATE.md` passing
8. **Only class-A resolves internally** — Class-B/C/D questions escalate to the user. Run `researcher` on class-B before escalating. Batch B and C.
9. **Sealed nodes** — Cross-node contracts do not change without an explicit ADR in `docs/adr/`
10. **No generic dicts** — All cross-module handoffs use typed domain objects only
