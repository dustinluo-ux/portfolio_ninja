# Question Classifier

Classify every question before deciding whether to ask the user.
Only class A must be resolved internally. Classes B, C, and D are escalated to the user.

---

## Classes

### A — Technical / Reversible
Decision is derivable from code, docs, web research, or established convention. Can be changed cheaply later.

**Action:** Resolve internally. No log required.

**Examples:** Library selection for < 50 LOC task, naming conventions, log level, test fixture structure, helper function design.

---

### B — Technical / Irreversible
Technical decision that is hard or costly to change after implementation begins.

**Action:** Use `researcher` agent first. Then ask user — batch with class-C questions if any are pending. Provide 2–4 options and a recommendation informed by research.

**Examples:** Database schema, API response envelope format, serialization format (JSON vs MessagePack), async vs sync I/O model.

---

### C — Business / Product / Valuation
Requires business intent, pricing knowledge, market context, or regulatory information that an agent cannot derive.

**Action:** Ask user. Batch all class-B and class-C questions in a single message with 2–4 options and a recommendation.

**Examples:** Pricing model, target market segment, approved data sources, budget ceiling, what is explicitly out of scope.

---

### D — Security / Credential / Destructive
Involves credentials, secrets, external accounts, production data, or irreversible operations.

**Action:** Ask user unconditionally. No exceptions.

**Examples:** Writing to `.env`, force-pushing to main, dropping database tables, changing auth model, adopting paid external services.

---

## Quick Reference

| Class | Type | Action |
|-------|------|--------|
| A | Technical / reversible | Resolve internally |
| B | Technical / irreversible | Research first → ask user, batch with C |
| C | Business / product | Ask user, batch with B, 2–4 options + recommendation |
| D | Security / destructive | Ask user, no exceptions |

---

## Batching Rule

B and C questions are batched together in one message. Run `researcher` on all B questions first so recommendations are informed. D questions are never batched — each gets its own message.

## Logging Rule

Class-B/C/D awaiting user input:
- Add to `STATE_HANDOFF.md` under **Open Questions** with the class noted
