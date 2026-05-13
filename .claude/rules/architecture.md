# Architecture Rules

## Case Facts Rule (mandatory for all subagents)

Every subagent invocation — architect, contract-writer, risk-checker, builder, spec-reviewer, code-reviewer, reviewer, integrator — **must prepend the full contents of `{TARGET}/docs/CASE_FACTS.md` verbatim to its context** before performing any work.

Rules:
- Read the file as-is. No summarizing. No paraphrasing.
- If `CASE_FACTS.md` does not exist at `{TARGET}/docs/`, halt and surface to the user before proceeding.
- Any field containing `{PLACEHOLDER}` means it was not filled in. Treat unfilled fields as open questions requiring human input — do not assume values.
- Decisions listed in the **Decisions Made** table are binding. Do not re-litigate them.
- Items in the **Open Questions** table must be escalated via `status: NEEDS_HUMAN`; do not guess.
- Items in **Out of Scope** must not be implemented under any circumstances.

## Path Confirmation Rule

Before scaffolding any new project: confirm the target directory explicitly with the user. Never default to `~/projects/`, `~/code/`, or any assumed location. Ask once if not stated.

## Repo Scaffold Standard

Every manufactured project must contain at minimum:

```
project/
  src/
  tests/
  .env.example
  CLAUDE.md          # project-level, inherits factory rules
  docs/ARCHITECTURE.md
  docs/contracts/
  README.md          # written after reviewer PASS
  STORY.md           # progress log, append-only
  pyproject.toml     # or package.json for JS projects
```

## ADR Convention

Architectural decisions live in `docs/adr/NNNN-title.md` (MADR format). Required fields: Status, Context, Decision, Consequences.

## Single Point of Failure Rule

Before any plan is approved, the planner must name exactly one SPOF per milestone. If multiple SPOFs exist, decompose into sub-milestones until each has exactly one.

## Sealed Node Architecture (portfolio_ninja-specific)

All 11 modules are sealed nodes. Cross-node contract changes require an ADR entry in `docs/adr/` before any implementation proceeds. The ADR gate hook enforces this on every `git commit`.

Domain objects are the only permitted cross-module interface. No generic dicts, no loosely-typed kwargs, no string-based dispatch between modules.

## API Design

- REST: plural nouns, versioned (`/v1/`), no verbs in paths.
- All responses: `{ data, meta, errors }` envelope.
- Auth: Bearer JWT only. No API keys in query strings.

## Dependency Policy

- Prefer stdlib over third-party for < 50 LOC tasks.
- Every new dependency requires a one-line justification comment in `pyproject.toml` / `package.json`.
- No dependency with < 1000 GitHub stars unless explicitly approved.

## Agent Naming

Session-utility agents live globally in `~/.claude/agents/`: `researcher` and `compressor`.
Pipeline agents live in `.claude/agents/` in this repo.

All agents use descriptive names:
- `architect` — decomposes idea into modules + execution graph; produces `docs/ARCHITECTURE.md`. Read-only.
- `contract-writer` — writes module contracts to `docs/contracts/`; updates `CONTRACT_INDEX.md`
- `risk-checker` — validates risk register + SPOF coverage; blocks pipeline on open critical risks
- `builder` — implements against approved contracts only; reports DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED
- `spec-reviewer` — verifies code matches contract spec (required outputs, no extra scope)
- `code-reviewer` — verifies code quality (coverage, naming, Decimal rule, atomic writes)
- `reviewer` — two-stage wrapper: dispatches spec-reviewer then code-reviewer in sequence
- `integrator` — end-to-end sweep after all builds; runs after all review stages PASS
- `researcher` — web research before any business/design question is escalated to user
- `compressor` — context compaction; writes STATE_HANDOFF.md
