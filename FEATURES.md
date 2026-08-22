# ReconAI — feature spec and dashboard walkthrough

Visual: **`dashboard_mockup.svg`** (every number in it is pulled live from
`data/ground_truth.csv`, so the mockup and the build cannot drift apart).

---

## The 13 features

### Summary layer

**1. Batch summary strip** — five metrics across the top.
`Records processed 265` · `Auto-matched 192 (72.5%)` · `In flight 19` ·
`Needs action 54` · `Resolved without AI 90.6%`

**2. Cost-efficiency stat** — the "resolved without AI" tile is deliberately
one of the five, always on screen. It is the answer to *"why not just
ChatGPT?"* rendered as a number you never have to argue for.

**3. Tier breakdown bar** — a single stacked bar showing how many records each
rung of the waterfall resolved, with a labelled legend underneath.
Tier 0: 24 · Tier 1: 82 · Tier 2: 60 · Tier 3: 19 · Tier 4: 56 · Tier 5: 24.
This is the audit trail in one glance: the green mass on the left is
deterministic work, the thin purple slice is the only place AI touched money.

**4. Money position panel** — the rupee view, not the record view:
order book value, settlements received, explained deductions, awaiting COD
remittance, and unexplained/at risk. A finance reviewer thinks in money first.

### Working layer

**5. Matched transactions table** — expected vs received side by side, the
delta, what the deduction was tagged as (gateway fee vs COD collection fee),
which tier resolved it, and whether it was deterministic or AI-assisted.

**6. Exception queue** — every unresolved record, with `PRIORITY`, `ORDER`,
`MODE`, `REASON`, `AGE`, `TIER`, `AI EXPLANATION`, and `AMOUNT AT RISK`.

**7. Priority-sorted exception queue** *(your addition)* — default sort is
amount at risk, descending, with a High/Medium/Low badge computed from the
size of the discrepancy. The Rs 9,999 unmatched order sits at the top; the
day-0 COD order that is simply waiting sits at the bottom. Re-sortable by
date, tier, or order ID, but highest-impact-first is what loads.

**8. Discrepancy amount as its own column** — the rupee figure is a column,
not buried inside the reason text, so the ranking is visible rather than
implied by row order.

**9. Exception reason legend** — the five reason codes rendered with plain
descriptions, so "still waiting" is never mistaken for "broken":
R1 Awaiting courier remittance (19) · R2 Remittance overdue (5) ·
R3 Unmatched / ambiguous (24) · R4 Partial payment (14) ·
R5 Large variance flagged by AI (11)

**10. COD remittance tracker** — three tiles, Fresh (12, 0-7d, no action) /
Approaching (7, 8-14d, watch) / Overdue (5, 15+d, chase courier), so COD
ageing is visible as a clock rather than hidden in the exception list.

**11. AI reasoning viewer** — opens on any Tier 3 row. Shows the facts the
engine computed and handed the model, then the model's one-sentence verdict.
The split is the point: *facts above, judgement below.*

### Control layer

**12. Payment mode filter + search** — filter the entire view by UPI, Card,
Netbanking, Wallet, or COD; search any order ID, gateway ref, or UTR.

**13. Run reconciliation + Export report CSV** — one button re-runs the
engine live during the demo, one exports the full result set.

**14. Chat assistant** — floating widget, bottom-right, collapsed by default.
Answers questions about the results table already in memory, using the same
model client Tier 3 uses. Read-only, current run only, no external lookups.
Out-of-scope questions get a refusal rather than a guess. A thin nod to the
track's "Settlement Q and A" direction without building it as a subsystem.

**15. Cosmetic sign-in screen** (`login_mockup.svg`) — visual polish only.
No identity is verified, no credentials are checked, nothing is stored; any
input proceeds. Labelled as such on the screen itself so it can never be
mistaken for a security claim. Pitch line: *"in production this sits behind
the company's existing SSO."*

---

## How a reviewer actually uses it

1. **Land on the dashboard.** Read one number: `Needs action 54`.
2. **Glance at the tier bar.** Confirm the deterministic layers did the bulk
   of the work and AI touched only 19 records.
3. **Go straight to the exception queue.** It is already sorted by money at
   risk, so the first row is the biggest problem in the batch.
4. **Work down the list.** Reason tag tells you *what kind* of problem;
   amount tells you *whether it is worth your next ten minutes.*
5. **Click "View reasoning"** on Tier 3 rows to see why the AI flagged it.
6. **Ignore the Low/blue rows** — those are healthy in-flight COD, shown for
   completeness, not action.
7. **Export CSV** and take it to the courier or the gateway.

---

## Two framing decisions baked into the visual

**In-flight is separated from needs-action.** The 19 COD orders inside their
normal window are counted in their own tile, not in the exception total.
Folding them in would inflate the failure count to 73 and make an honest
system look worse than it is.

**Priority is computed from money, but Tier 0 rows are capped at Medium.**
An overdue Rs 9,999 COD remittance and an unmatched Rs 9,999 payment are the
same rupees but not the same urgency — one is a courier who is late, the other
is money that may not exist. The badge reflects that; the sort still respects
the amount.
