# Ledgr — Claude Code Instructions

## Read First

Before doing any work on this project:

1. Read `PROJECT_CONTEXT.md`.
2. Inspect the existing repository.
3. Understand the existing reconciliation architecture.
4. Do not assume the codebase is empty.
5. Do not assume previous Claude sessions are available.

`PROJECT_CONTEXT.md` is the persistent project memory.

---

## Critical Rules

### Do NOT rewrite the reconciliation engine casually.

The existing deterministic reconciliation logic is important.

Do not modify:
- `reconcile()`
- matching rules
- tier definitions
- financial calculations

unless the user explicitly approves the change.

### Inspect before modifying.

Before editing code:
- inspect relevant files
- explain what currently exists
- identify the exact change required

### AI must augment deterministic reconciliation.

The AI Forensic Agent should investigate flagged cases.

It should NOT replace the deterministic reconciliation engine.

### Never invent financial evidence.

If information is unavailable:
- state that it is unavailable
- do not fabricate evidence
- do not fabricate Razorpay API results
- do not invent transaction history

### Preserve human review.

Ambiguous or insufficiently supported cases should be routed to Pending Review when appropriate.

---

## Development Process

Use this workflow:

1. Understand.
2. Inspect.
3. Explain.
4. Plan.
5. Get approval for major changes.
6. Implement.
7. Test.
8. Report what changed.

Do not make large architectural changes without discussing them first.

---

## Communication

Explain technical decisions in simple language.

When proposing a change, explain:

- what is changing
- why it is needed
- where it fits
- what existing behavior it preserves
- how it will be tested

Prefer small, understandable changes over unnecessary rewrites.