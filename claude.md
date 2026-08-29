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

---

## AI Agent Implementation Strategy (Aug 26, 2026)

### Key Architectural Decisions

#### 1. Hybrid Approach: If-Else + LLM + Human Review

**DO NOT use AI for everything.** Use this priority:

1. **If-Else for simple cases (Tier 1 & 2)** - 85-90% of records
   - Exact amount match → Auto-clear
   - Known fee deduction within tolerance → Auto-clear
   - Fast, free, deterministic

2. **LLM for complex reasoning (Tier 3)** - 5-10% of records
   - Amount variance outside tolerance
   - Unknown deduction patterns
   - Requires reasoning and explanation
   - Uses Claude API for investigation

3. **Human review for ambiguous cases (Tier 5)** - 2-5% of records
   - Multiple possible matches
   - Low AI confidence (<70%)
   - High financial risk
   - AI prepares evidence, human decides

#### 2. AI vs ML vs Agentic AI

**We are using: LLM-based AI (Claude API)**

Why NOT traditional ML:
- ❌ Requires 1000s of labeled training examples
- ❌ Cannot explain reasoning
- ❌ Cannot handle new scenarios
- ❌ Cannot generate text (emails, explanations)

Why NOT full agentic AI:
- ❌ Too complex for buildathon scope
- ❌ Slower (5-10 seconds per case)
- ❌ More expensive (multiple API calls)
- ❌ Less predictable

**LLM approach:**
- ✅ No training data needed
- ✅ Explains reasoning in plain English
- ✅ Handles new scenarios
- ✅ Generates actionable outputs (emails, next steps)
- ✅ Fast enough (2-3 seconds)
- ✅ Buildathon-appropriate complexity

**Optional: Light agentic features**
- AI suggests what data to check
- Human/code fetches the data
- AI analyzes and concludes
- Gives some autonomy without full complexity

#### 3. When AI Is Actually Needed

**AI is NOT needed for:**
- ✅ Direct UTR matching (COD with bank_utr)
- ✅ Direct gateway_ref matching (online payments)
- ✅ Normal fee deductions (within 2-3% tolerance)
- ✅ Known refunds (Razorpay API shows refund amount)
- ✅ International cards (binary check: international = 5% MDR)

**AI IS needed for:**
- ⚠️ Ambiguous matches (2+ candidates with same name/amount)
- ⚠️ Unknown variance (large shortfall, no clear reason)
- ⚠️ Complex patterns (customer behavior, fraud detection)
- ⚠️ Missing/incomplete courier data
- ⚠️ Multi-step reasoning required
- ⚠️ Generating human-readable explanations

#### 4. Real-World COD Reconciliation

**Ideal scenario (20% of cases):**
- Courier sends detailed remittance report with order IDs
- Each order has bank_utr updated
- Amounts match exactly after known fees
- → Simple if-else matching, no AI needed

**Real scenario (80% of cases):**
- Courier sends bulk payment (1 UTR for 15 orders)
- Courier report missing or incompatible format
- Courier report has errors/missing orders
- Multiple couriers with different formats
- Timing mismatches between reports and bank statements
- → AI helps match orders, detect discrepancies

**Common COD problems:**
1. **Customer paid less** - Complained about damage, delivery guy accepted partial payment
2. **Courier deducted penalties** - RTO charges, packaging fees not disclosed upfront
3. **Cash handling errors** - Miscounted, lost notes, wrong change given
4. **Doorstep returns** - Customer returned old order, delivery guy adjusted amount
5. **Bulk remittance ambiguity** - ₹50k for 15 orders, which 15?

#### 5. Customer History Usage

**Why customer history matters:**

1. **Ambiguous matching** - When 2 customers have same name:
   - Customer with 100% payment history (3/3 paid) → Higher confidence
   - Customer with 0% history (rejected last order) → Lower confidence
   - AI weighs reliability as a matching factor

2. **Fraud detection** - Large orders from new customers:
   - New customer, first order ₹1,200 → Paid ✓
   - Same customer, second order ₹25,000 → FRAUD RISK!
   - Pattern: Fraudsters test with small order, then place huge order

3. **Behavior patterns** - Customer switched payment methods:
   - Past: Used COD, one rejection
   - Now: Uses UPI consistently
   - If order marked COD but paid UPI → Expected behavior, not error

4. **Trust scoring** - Calculate confidence:
   - 5+ orders, 95%+ success → Trust score 0.95 (high confidence)
   - 0 orders → Trust score 0.30 (low confidence)
   - Used in ambiguous matching decisions

**IMPORTANT:** Customer history is a **secondary factor**, not primary matching criteria.
- Primary: UTR, gateway_ref, amount
- Secondary: Customer history helps resolve ambiguity

#### 6. Data Quality Assumptions

**DO NOT assume perfect data:**
- ❌ UTR is not always present (bulk remittances, system lag)
- ❌ Courier reports are not always available
- ❌ Amounts don't always match (customer complaints, penalties)
- ❌ Payment modes can change (customer switches at checkout)
- ❌ Data formats vary across couriers

**The AI layer exists specifically to handle imperfect data.**

#### 7. Razorpay API Integration

**API is used for evidence collection, not primary matching.**

**What Razorpay API provides:**
- Payment status (captured/failed)
- Actual fee charged
- Card type (international/domestic)
- Refunds issued
- Disputes/chargebacks
- Payment method details

**How it's used:**
1. Tier 3 variance detected → Call Razorpay API
2. AI analyzes: order + settlement + API data
3. AI explains variance using evidence
4. High confidence → Auto-clear with explanation
5. Low confidence → Flag for human review

**API is optional:**
- Without API: AI works with CSV data only (lower confidence)
- With API: AI has more evidence (higher confidence)

#### 8. Tier 0 COD Aging

**Already implemented correctly in engine.py:**
- 0-7 days: "AWAITING_REMITTANCE" (normal, no action)
- 8-14 days: "APPROACHING_THRESHOLD" (monitor, not critical)
- 15+ days: "EXCEPTION" (overdue, escalate to courier)

**COD pending is NOT a reconciliation failure** - it's a clock running.

Only after 15+ days does it become an exception requiring action.

AI can help: Draft escalation email to courier when overdue.

#### 9. Implementation Priorities

**Phase 1: Core AI Forensic Agent**
- Replace `_llm_diagnose()` stub with Claude API
- Evidence collection from CSVs + Razorpay API
- Structured diagnosis output (reason, confidence, actions)
- Confidence-based routing (>90% auto-clear, <70% human review)

**Phase 2: UI Integration**
- Show AI investigations in dashboard
- "AI Auto-Cleared" category (separate from manual matches)
- Evidence panels (what AI checked, what it found)
- Draft messages (emails to Razorpay, customers, couriers)

**Phase 3: Pattern Detection (Optional)**
- Detect systematic issues (courier delays, gateway overcharging)
- Aggregate insights across batch
- Proactive alerts

**Phase 4: Light Agentic Features (Optional)**
- AI suggests what to investigate
- Dynamic evidence collection
- Multi-step reasoning

#### 10. Buildathon Focus

**Primary value proposition:**
"Ledgr uses AI to explain payment variances that deterministic rules cannot handle, reducing manual investigation time by 85%."

**NOT:**
- ❌ "AI matches all payments" (false - if-else matches 90%)
- ❌ "AI replaces reconciliation engine" (false - augments only)
- ❌ "AI handles perfect data" (false - handles messy data)

**Demo scenarios to showcase:**
1. International card (5% MDR) - AI verifies via API, auto-clears
2. Refund detected - AI finds refund in API, explains shortfall
3. Ambiguous match - AI weighs evidence, suggests match with confidence score
4. Unknown variance - AI investigates, drafts email to Razorpay
5. Pattern detection - AI notices systematic courier delays across multiple orders

---

## Technical Constraints

### Never Auto-Clear Without Justification




High confidence (>90%) alone is not enough to auto-clear.

**Required for auto-clearing:**
1. Confidence >90%
2. Evidence is complete (all APIs called, no gaps)
3. Financial risk is low (variance is explainable)
4. Pattern matches known good scenarios

**Always flag for human review if:**
- Confidence <70%
- Evidence has gaps (API unavailable, data missing)
- Financial risk is high (large amount, fraud indicators)
- First occurrence of a pattern (no historical validation)

### API Call Hygiene

**Razorpay API calls:**
- Use proper authentication
- Handle rate limits (max 10 calls/second)
- Handle failures gracefully (API down = flag for review, don't crash)
- Cache responses (don't call same payment_id twice)
- Never expose API keys in logs/UI

**If API fails:**
- ❌ Do NOT auto-clear
- ⚠️ Flag: "Could not verify via Razorpay API (service unavailable)"
- ✅ Provide manual review option with partial evidence

### Confidence Scoring

**Be conservative with confidence scores:**

90-100%: Only when all evidence points clearly to one conclusion
- Example: API confirms international card, fee matches exactly 5%

70-89%: High confidence but some uncertainty remains
- Example: Ambiguous match, but strong customer history supports one candidate

40-69%: Multiple plausible explanations
- Example: Large variance, could be chargeback or reserve hold

0-39%: Insufficient evidence or highly ambiguous
- Example: Settlement with no matching order candidates

**Default to human review when in doubt.**

---

## Future Enhancements (Post-Buildathon)

1. **Multi-courier normalization** - Handle BlueDart, DTDC, Delhivery formats automatically
2. **Webhook integration** - Real-time reconciliation as payments arrive
3. **ML fraud detection** - Train model on historical fraud patterns (requires labeled data)
4. **Bulk actions** - "Approve all 15 AI suggestions" with one click
5. **Learning from corrections** - When human overrides AI, learn from it
6. **Settlement prediction** - "Order ORD-123 should settle by Aug 27" based on patterns

---

## Session Context (Aug 26, 2026)

**Discussion with user covered:**
- AI vs ML vs Agentic AI (why LLM is right choice)
- When AI is needed vs when if-else suffices
- Real-world COD reconciliation problems (messy data, bulk remittances)
- Customer history usage (trust scoring, fraud detection)
- Data quality assumptions (UTR not always present, couriers send incomplete reports)
- Identified loopholes in initial examples (simplified scenarios vs real-world complexity)

**User's key insights:**
- COD should match by UTR when available (primary method)
- Payment amounts should match invoice (delivery guy knows amount)
- Couriers should send order lists (in ideal case)
- → Agreed: AI is for the 80% "messy data" cases, not the 20% "perfect data" cases

**Major Architecture Shift (Aug 26, 2026 afternoon):**

User proposed moving from **CSV upload tool** to **SaaS platform** with:
1. **Login/authentication** - Company-specific SSO credentials
2. **Auto-fetch orders** - From merchant's e-commerce platform (Shopify/WooCommerce/custom API)
3. **Auto-fetch settlements** - From Razorpay API directly
4. **Incremental sync** - Only fetch new data since last sync (timestamp-based)
5. **Multi-merchant isolation** - Each company sees only their data

**Critical implementation decisions for buildathon (10 days left):**

### What to Build (REAL):
1. **Simple login** (hardcoded 3-4 demo accounts, NOT full OAuth SSO)
2. **Real Razorpay API integration** (fetch settlements + payment details)
3. **Mock Shopify/merchant API** (simulate with pre-prepared realistic JSON data)
4. **Settings page** (show integration status, API key config)
5. **Auto-sync dashboard** ("Sync Now" button, progress indicators)
6. **Keep existing engine.py** (DO NOT rewrite reconciliation logic)
7. **CSV upload backup** (safety net if demo breaks)

### What NOT to Build (too complex for timeline):
- ❌ Real OAuth/SSO with Google/Microsoft
- ❌ Real Shopify/WooCommerce API integration
- ❌ Database with encryption (hardcode credentials for demo)
- ❌ Webhook infrastructure
- ❌ Multi-gateway support beyond Razorpay

### Incremental Sync Strategy:
```python
# Store last_sync_timestamp per merchant
# Fetch only NEW data:
GET /api/orders?created_after=2026-08-26T10:30:00Z
GET /v1/settlements?from=1724665800

# Razorpay API naturally isolates by API key
# Filter Shopify orders by payment_gateway_names = ["razorpay"]
```

### 10-Day Timeline:
- Day 1-2: Login screen + session management
- Day 3-4: Real Razorpay API integration (test mode)
- Day 5: Mock merchant API (realistic demo data)
- Day 6: Settings page (integrations UI)
- Day 7: Auto-sync dashboard
- Day 8-9: AI Forensic Agent (Claude API)
- Day 10: Polish + demo prep

**Next immediate task:**
- Update PROJECT_CONTEXT.md with new architecture
- Start building login screen (decide: Streamlit vs React)
- Create 3-4 demo merchant accounts

---

## Session Update (Aug 26-27, 2026): Login built, Razorpay client built and verified, AI case taxonomy defined

### Files added/changed this session
- `theme.py` — new. Single source of truth for colors/fonts/CSS shared by `login.py` and `app_new.py`, matching `app.py`'s existing palette (Inter font, `#1A56DB` accent, thin borders — never the purple gradient an earlier pass invented). Also exports `html()` — see gotcha below.
- `login.py`, `app_new.py` — rewritten to use `theme.py`, fixed multiple real rendering bugs (below), redesigned as a split panel (brand story + live reconciliation preview on the left, sign-in form on the right).
- `auth.py` — demo password check is now case-insensitive/whitespace-trimmed (these are fake demo creds, not real secrets — caps-lock/autofill shouldn't break a demo login).
- `razorpay_client.py` — new. Isolated module, real REST calls (via `requests`, not the `razorpay` SDK) to `GET /v1/settlements/` and `GET /v1/settlements/recon/combined`, reading `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` from `.env` (via `python-dotenv`). Exposes `connection_status()` returning one of `STATUS_OK` / `STATUS_EMPTY` / `STATUS_AUTH_ERROR` / `STATUS_API_ERROR` plus rows plus a message — never fabricates rows on empty/error.
- `.env` / `.env.example` — `.env` already gitignored (pre-existing `.gitignore` entry). `.env.example` has placeholders only, safe to commit.
- **Verified against the user's real Razorpay Test Mode keys:** authentication succeeded, 0 settlements returned. This is the *expected* result, not a bug — see below.

### Streamlit gotchas discovered the hard way — avoid repeating these

1. **A `<div>` opened in one `st.markdown()` call and closed in a later one does NOT wrap anything.** Streamlit renders each `st.markdown()` call as an isolated HTML fragment; the browser auto-closes the dangling div immediately. Symptom: card looks like it has no border, because it never actually contained the widgets between the two calls. Fix: use `st.container(border=True)` (or `st.container(key="...")` + CSS targeting `.st-key-...`, the same technique `app.py` already uses for `brandbar`/`choices`/etc.) for anything that needs to visually wrap real Streamlit widgets.
2. **`st.markdown(..., unsafe_allow_html=True)` still runs the string through a Markdown parser first** — `unsafe_allow_html` only stops HTML from being escaped, it does not disable Markdown's own block rules. A blank line in the middle of an HTML literal (easy to introduce by joining several `f"""\n...""" ` fragments) resets the block context, and the next indented lines (indentation comes for free once the literal sits inside a few nested `with` blocks) get parsed as a fenced *code* block — text shows up literally instead of rendering. Fix: `theme.py`'s `html()` helper strips per-line leading whitespace before anything reaches `st.markdown()`. Route every multi-line HTML literal through it.
3. Streamlit 1.62's "Deploy" toolbar needs `[data-testid="stToolbar"]` (and `stDecoration`, `stStatusWidget`) hidden explicitly — the older `.stDeployButton` class alone doesn't catch it anymore.

### Razorpay Test Mode — confirmed facts, don't relitigate these
- **Test Mode never generates real settlements**, no matter what — no real money moves, so there's nothing to settle. Confirmed via Razorpay's own docs. A 0-result `connection_status()` call is success, not failure — display it as "Connected, no live settlements available," never as an error.
- **Razorpay is not involved in COD at all.** COD cash is collected by the courier and remitted to the merchant's bank directly — Razorpay has zero visibility into that money. Confirmed by the existing `data/settlements.csv` itself: `BANK`-sourced rows have empty `gateway_ref_id`, only `bank_utr` — structurally different from `RAZORPAY`-sourced rows. Do not build or imply a Razorpay-based path for COD settlement data.
- **`GET /v1/settlements/` alone cannot satisfy `SETTLEMENT_REQUIRED`** — it returns settlement *batch* headers (id, amount, utr, created_at) with no per-payment reference, so it can never populate `gateway_ref_id`. `GET /v1/settlements/recon/combined` is the endpoint with `payment_id` + `settlement_id` together — that's the one mapped to our schema in `razorpay_client.py`'s `to_settlement_rows()`.
- **Razorpay's Orders API is explicitly NOT used for order data.** Orders always come from the merchant's e-commerce platform (Shopify, mocked for the buildathon) — never from Razorpay, even though Razorpay does have an Orders API. Settlements-only from Razorpay.
- Shopify's Fulfillment object has a `tracking_company` field (confirmed via Shopify docs, includes DTDC) — this is where the courier name for Case 7 (escalation emails) should come from once real Shopify order fetching exists. `orders.csv`'s current schema has no courier field at all.

### Three data sources, not two — keep this straight
1. **Orders** — merchant's e-commerce platform API (Shopify, mocked for buildathon).
2. **Online settlements** — Razorpay API (real, built, verified).
3. **COD/bank settlement data** — neither of the above. Razorpay never sees COD cash; getting this "for real" would mean a bank Account Aggregator integration or direct courier remittance APIs, both explicitly out of scope (see existing "what NOT to build" list). For the buildathon this stays synthetic (`gen_data.py`'s `BANK`-sourced rows) or manual CSV upload — the same mechanism `app.py` already has. When live Razorpay settlements exist, **merge** them with the local COD/bank file (both already share one schema via the `source` column) rather than replacing it.

### Sync semantics — do not reconcile incrementally
`engine.reconcile()` is stateless and has no concept of "new" data. **Sync (fetching) is incremental — avoid re-fetching what's already stored — but reconciliation must always run on the full cumulative dataset.** Reasoning: an order fetched today might not get its settlement until T+2 days later; if you only reconcile "today's new batch," that later settlement has nothing in scope to match against and shows as a false-positive orphan purely due to sync timing, not because it's actually unmatched. Previously-unresolved exceptions will naturally re-appear on every rerun (the engine has no memory) — that's expected, not a bug; `review_log.csv` (already exists, append-only, `record_id,resolved_at,note`) is what suppresses already-resolved records from the "needs attention" view without ever deleting or mutating the underlying data.

**Retention policy agreed with the user:** unresolved orders/settlements are kept indefinitely. For resolved duplicate-payment cases specifically: keep a lightweight permanent audit record (`record_id`, outcome, resolved-at — same shape as `review_log.csv` already provides) forever, but the heavyweight investigation evidence (full API payloads, correlation reasoning) can be pruned after 7 days. Never hard-delete the fact that a case was flagged and resolved — that's the audit trail a chargeback dispute weeks later would need.

**Future optimization, not needed yet:** at real production scale, re-walking the entire historical order/settlement set on every sync is wasteful even though `reconcile()`'s O(N+S) hash-map approach isn't quadratic. The correct fix (same pattern real AR/bank reconciliation systems use) is an "open items" ledger — archive records that reached a terminal state (cleanly matched, or human-resolved) out of the working set permanently; only ever reconcile the still-open backlog plus newly-fetched data. Partition by *state* (resolved vs. not), never by *time*/sync-batch, or you reintroduce the false-orphan bug above. Not worth building at demo data volumes (hundreds–thousands of rows) — document only.

### AI Forensic Agent — the 7-case taxonomy (supersedes the vaguer "when AI is needed" list earlier in this file)

Grounded directly in `engine.py`'s actual tiers/paths, not abstract categories:

| # | Case | Where in `engine.py` | AI's real role | Engine changes needed? |
|---|---|---|---|---|
| 1 | Genuine unexplained variance (matched, amount outside band, no refund/dispute/fee explains it) | Tier 3/4, `:188-196`, calls `ai_diagnose()` | True AI — reasoning over absence of evidence | No, already wired (stub only, see `_llm_diagnose`) |
| 2 | Duplicate/overpayment | Manifests as an **orphan settlement**, Tier 5 `:199-205` — NOT a same-order 2x-delta (a single `payment_id` can't be captured twice for double its amount; the real mechanism is a checkout retry creating a *second, separate* Razorpay order, since Razorpay's own same-order duplicate guard only protects one order_id) | Mixed — correlating a settlement with no matching order to a likely sibling order via customer/amount/time-window signals; drafts refund recommendation, never executes it | `ai_assisted` flag (`emit()`, `:120`) doesn't cover this path today — needs wiring |
| 3 | Ambiguous multi-candidate match (2+ settlements claim same ref/UTR) | Tier 5, `:159-166` | True AI — weighing near-identical candidates via soft signals | No, just needs a call added |
| 4 | Order with zero matching settlement at all | Tier 5, `:153-157` | Mostly a lookup — check the payment's actual status via Razorpay (`captured` = still just settlement lag; `failed`/auto-refunded after 3 days = order record is wrong, don't wait forever) | No |
| 5 | COD bulk remittance (one UTR covers many orders) | **Not modeled** — `by_utr` (`:103-108`) is strictly 1:1 today | True AI — ambiguous subset-sum/partition problem | **Yes, real architectural gap** — needs explicit user approval per this file's own rules before touching |
| 6 | Free-text/inconsistent courier narration (bank narration format varies per courier per bank, breaks any fixed regex) | The `narration` field, currently just displayed raw | True AI — unstructured input, and must be able to honestly say "insufficient information" rather than force a wrong match | No |
| 7 | Human-facing text generation (escalation emails, refund recommendation drafts) | Tier 0 overdue (`:132-135`), and as the output layer for any case above | True AI — pure generation, zero financial-decision risk since a human reviews/sends the draft | No — but needs a `courier`/`delivery_partner` field added to the order schema first (see gap below) |

**The organizing principle — apply this before adding any new AI call:** AI earns its place only where a deterministic lookup structurally cannot answer the question (ambiguity, absence of evidence, unstructured text, or generation). If the recon/evidence data already contains a field that answers it — e.g. a refund row matching the delta exactly — that's a plain lookup/join, not an AI call. **Tier 3 should be two sub-stages, not one:** 3a (deterministic — cross-check the flagged delta against the full Razorpay recon table for that `payment_id`; auto-explain/clear on a match, zero AI, zero cost) and 3b (real AI — only the leftovers 3a couldn't explain, or genuinely ambiguous/textual/multi-signal cases). This is cheaper, faster, and has zero hallucination risk for the cases it covers.

**Non-negotiable, regardless of AI confidence:** anything that involves *moving money* (a refund) requires human approval before execution, even at 95%+ confidence. AI's ceiling is "produce the evidence-backed recommendation, draft the action" — never "execute the refund unattended." This is stricter than this file's general confidence-based routing table above, specifically because refund cases are outcomes, not just explanations.

### Real schema gaps confirmed by re-reading schema_map.py (not yet fixed)
- No customer phone/email in `ORDER_OPTIONAL` (only `customer_name`) — needed to correlate an orphan settlement (Case 2) or disambiguate near-duplicate candidates (Case 3) with any confidence beyond amount/date proximity alone.
- No `courier`/`delivery_partner` field in `orders.csv` at all — Case 7's overdue-COD escalation email currently has no addressee. Once real Shopify order fetching exists, `tracking_company` on Shopify's Fulfillment object solves this for free (confirmed supported, includes DTDC) — but it doesn't exist in the schema yet and the mock data doesn't have it either.

### Why call real APIs at all — the honest pitch, for judges
Verified: payment reconciliation via API (vs. manual CSV) is a real, established SaaS category (Airwallex, Payrails, Taxilla etc. all sell this, with the exact same "legacy = manual CSV, modern = API-native" framing). But be precise about *which* API call is the strong argument: the **bulk settlement fetch is useful automation but table-stakes** — every competitor claims it. The **defensible, hard-to-replicate value is the Tier-3 payment-fetch evidence call** — pulling live, on-demand detail (refund status, dispute status, card type) for one specific flagged payment, which a static CSV export can never contain no matter how automated. Pitch this as "the API matters because our AI agent needs live per-transaction evidence," not "we automated an upload click."

---

## Session Update (Aug 27, 2026): Dashboard rebuilt as HTML shell + minimal widgets

Redesigned `app_new.py`'s post-login dashboard end to end (command-center layout: header with account dropdown, three source-status cards, last-reconciliation block, Sync & Reconcile CTA, activity log). Getting the layout precise took several rounds of real bugs — the lessons below are worth reading *before* touching this page's CSS again, not after re-discovering them.

### The core architectural lesson: HTML shell for structure, st.columns() for placement, CSS only for visual styling

Early attempts tried to control layout (centering, right-alignment, overlay positioning) by overriding a Streamlit container's own `display`/`position` via a `.st-key-*` class. This lost the specificity fight against Streamlit's own CSS almost every time — three separate bugs (popover spacing, avatar landing on the wrong side, a button pinned to the page edge) all traced back to this. The fix that actually held: use real `st.columns()` for *where things sit* (Streamlit's own layout primitive, reliable every time it's been tried on this page), and scope custom CSS to *only* the innermost visual details (a button's own border-radius/color/padding) — never a container's own layout-determining properties. When in doubt, add a layout-only `st.columns()` split rather than fight a container's `display`/`position` with `!important`.

### Streamlit's current testid naming — verify camelCase, don't guess older names
`data-testid="element-container"` does not exist in this Streamlit version and silently matches nothing — a CSS rule targeting it will look plausible and simply do nothing, which is a nasty silent-failure shape (no error, just no effect). The correct current testid is `stElementContainer`, matching the camelCase convention already confirmed working elsewhere (`stVerticalBlock`, `stButton`, `stToolbar`, `stDecoration`, `stStatusWidget`). If a spacing/margin override targeting a testid appears to do nothing, suspect an outdated/wrong testid name first, before assuming a specificity problem.

### Overlay positioning (dropdown menus, popovers) that doesn't shift page content
A real Streamlit widget rendered conditionally in normal document flow will push everything below it down the page when it appears — there is no way around this while it stays in-flow, no matter how it's styled. For a true overlay (dropdown, tooltip, popover) that must not shift layout:
1. Give it `position: absolute` — this removes it from flow entirely, so it neither pushes siblings down nor expands its own parent's height.
2. Anchor it to a small, tightly-scoped positioned ancestor — nest it inside the same small `st.container(key=...)` as the specific element it should hang off of (e.g. an avatar button), not a wide ancestor (a whole header row). A wide/ambiguous positioning context is what caused the avatar-dropdown to drift to the wrong side in an earlier attempt.
3. But watch out: if that small ancestor also has an explicit `width` set (e.g. 36px to size an avatar circle), an element `position:absolute` inside it can still inherit that width constraint in practice and render squeezed down to a sliver (symptom: text wrapping one character per line). Fix: introduce one more layer — a wrapping container with no width constraint of its own (e.g. `rightslot`) as the actual positioned ancestor, with the width-constrained element (`avatarbtn`) and the overlay (`accountmenu`) as siblings inside it, not nested inside the narrow one.
4. `st.popover()` exists and works, but its rendered content sits in a portal-like structure whose internal testids proved unreliable to target confidently — after two failed styling attempts, it was dropped in favor of hand-rolling the toggle+overlay with `st.session_state` + a plain `st.button()`, which gave full control.

### Centering with st.columns()
`st.columns([2, 3, 1])` does not put the middle column's center at the row's true center — asymmetric flanks shift the middle column's own midpoint away from 50%. For true centering, flanks must be equal: `st.columns([1, 3, 1])`.

### Streamlit's own theme color can bleed through as a focus/hover state
A button styled only for its resting state can still show Streamlit's theme `primaryColor` (set in `.streamlit/config.toml`, currently a blue) on `:hover`/`:focus`/`:active`, since those pseudo-states aren't touched by a plain resting-state override. If a button unexpectedly shows the theme accent color when clicked, explicitly override `:hover`, `:focus`, and `:active` too, not just the base state.

### Login to dashboard transition
Streamlit reruns the entire script on every navigation — there is a real network round-trip on every `st.rerun()` that cannot be eliminated while staying on Streamlit (a constraint the user explicitly confirmed: keep Streamlit, don't introduce a new frontend framework). What's achievable instead: a CSS fade-in on `[data-testid="stMain"]` so new content eases in rather than popping in abruptly (in `theme.py`'s `base_css()`, shared by every page), and an explicit `st.spinner("Signing in...")` around the auth check so the wait is communicated rather than feeling like unexplained lag. This masks the abruptness; it does not make the round-trip itself instant — say so plainly if asked again, don't imply it's fully solved.

---

## Session Update (Aug 27-28, 2026): Incremental demo-data flow, persistent notifications, Dashboard/Reconciliations redesign

Three separate but related pieces of work landed together: (1) splitting the demo dataset into 3 deterministic batches that unlock over time via persisted timestamps, (2) a bell + auto-appearing overlay notification system for when a new batch arrives, and (3) a full redesign of the Dashboard and Reconciliations pages into a page-routed app shell (sidebar + header shared across pages, no more separate full-screen sync route).

### New files / major structural changes
- **`state_store.py`** (new) — per-merchant JSON at `data/state/<merchant_id>.json`. Holds `current_batch`, `processed_record_ids`, `reconciliation_runs` (each carrying its own `flagged_records` — see the AI session update below), `next_batch_available_at`, and the notification lifecycle fields (`notification_created`, `notification_seen`, `notification_overlay_open`). This is the file that makes refresh/logout-login safe — nothing here lives only in `st.session_state`.
- **`app_new.py`** — restructured around `st.session_state.current_page` (`"Dashboard"`, `"Reconciliations"`, `"AI Review"`, `"Exceptions"`, etc.). One shared shell function renders the sidebar (highlighting whichever page is active) and header (title/subtitle + bell + avatar) for every page; each page is just a body-rendering function called from one dispatcher. The old separate `show_sync_screen()`/`show_review_screen()` full-page routes are gone — syncing now happens *inline inside the Reconciliations page* (sidebar and header stay visible throughout).
- **`gen_data.py`** — scaled from ~924 orders (308/batch) down to exactly 180 orders (60/batch) per explicit user direction ("approximately 180 total, not 900-1000"). Same scenario taxonomy, same per-batch case-coverage principle (PLAN shuffled once, sliced into 3 contiguous chunks; special hand-built cases like the COD bulk-remittance group and shadow-duplicate settlement built once per batch, not concentrated in batch 1) — just smaller quotas and a smaller bulk-group/orphan-credit size (2 each per batch instead of 5) to land on the new target.

### The batch-availability / notification state machine
`state_store.batch_is_available(state)` is the single source of truth for "should batch N be revealed yet" — batch 1 is always available; batch 2/3 need `datetime.now() >= next_batch_available_at`, checked fresh on whatever rerun happens to occur. **No `time.sleep()`, no background thread, no polling loop anywhere in this path** — the timer is just a persisted timestamp compared on demand.

Notification lifecycle has three independent persisted flags per pending batch, not one:
- `notification_created` — has the "new data" event fired at least once for this batch. Set the instant the timer passes (checked at the very top of the main dispatcher, before any page-specific rendering, so it fires regardless of which page happens to be open). Gates whether the auto-overlay is even considered — **without this, the overlay would re-trigger on every rerun that finds the batch available, including after the user already dismissed it.**
- `notification_overlay_open` — should the floating card render *right now*. Set `True` alongside `notification_created`; set `False` by "Later"/"×" (dismiss without marking read) or by "Review & Reconcile" (dismiss *and* mark read). This is what lets the overlay persist across incidental reruns (e.g. the user clicks something else while it's showing) without needing to re-fire the "just discovered" event each time.
- `notification_seen` — drives the bell's red-dot badge. Explicitly **not** cleared by merely opening the bell panel (an earlier iteration did this and the user's own spec corrected it) — only clicking "Review & Reconcile" (from the overlay *or* the panel) clears it.

All three reset together in `schedule_next_batch()` whenever a new batch gets scheduled, and batch 1 is explicitly excluded from ever triggering any of this — it's the initial data, not a "new data received" event.

### The floating overlay: `position:fixed`, no positioned ancestor needed
Unlike the bell/avatar dropdowns (which need a `position:relative` wrapping ancestor per the overlay-positioning lesson above), a page-level toast like the new-data card uses `position:fixed` — it floats over the viewport by its own `top`/`right` coordinates regardless of where it sits in the DOM or what page is currently rendering, so it doesn't need the `rightslot`/`bellslot` wrapping-ancestor trick at all. Simpler than the dropdown case specifically because it isn't anchored to a specific small trigger element.

### Two-flag button-pair styling inside one small container
The overlay's "Later" / "×" pair sit in `st.columns([4, 1])` inside the same `st-key-newdataoverlay` container as the primary CTA. Styling them differently from the primary button by DOM position (`[data-testid="column"]:first-child`/`:last-child`) works reliably here because they're genuinely the only two columns in that specific row — this is safe positional CSS, unlike trying to use `:first-of-type` across a container that also holds unrelated markdown blocks (which silently matches the wrong element — the tag-type count includes non-button siblings). When in doubt, give a button its own `st.container(key=...)` wrapper instead of relying on structural CSS selectors.

### Recurring gotcha: a live `streamlit run` process caches old code AND old `.env` values
Hit **twice** in this project: once when `auth.py` gained a new function while a server was already running (`ImportError: cannot import name 'get_merchant_by_email'` — the running process had the old module body compiled in), and once when `.env` gained `RECONAI_LLM=1` and `engine.py` gained its own `load_dotenv()` call while a server was already running (the AI call silently kept using the offline stub because `engine.USE_LLM` had already been evaluated once, at that process's original import time, before either change existed). **A hard rule going forward: any time a `.py` file that's already imported gains a new top-level name, or `.env` gains/changes a value that a module reads at import time, the live `streamlit run` process must be fully killed and restarted — a browser refresh is not enough**, because Streamlit's file-watcher reruns the main script but does not re-execute already-imported modules' top-level code. Diagnose this class of bug by checking `netstat -ano | grep 8501`-style for a stale PID *before* assuming the new code itself is wrong.

### Building a real chart without a new dependency
No `plotly` installed, no `requirements.txt` tracking it — adding it wasn't warranted for one chart. The donut (Reconciliation Overview) stays a hand-rolled CSS `conic-gradient` (already built, zero dependency). The new Amount Flow chart uses `st.bar_chart()` — bundled with Streamlit itself (backed by Altair internally), zero install needed, and satisfies "use an existing charting solution if available" without introducing a library the project doesn't already depend on.

---

## Session Update (Aug 28, 2026): Real AI integration wired in — Gemini, not Claude

Phase 1 from this file's own "Implementation Phases" section (and `PROJECT_CONTEXT.md` Section 15) said "replace `_llm_diagnose()` stub with Claude API." **That's now done, but with Gemini, not Claude** — the user had a Google AI Studio key on hand, not an Anthropic one, and getting a fresh Anthropic key would have meant new signup + billing setup under buildathon time pressure. This is a plain provider swap, not a scope change: the whole point of `ai_client.py` being an isolated module (same shape as `razorpay_client.py`) is that engine.py never knows or cares which vendor sits behind `diagnose()`. Correct any future assumption in this file or `PROJECT_CONTEXT.md` that says "Claude API" — read it as "whichever LLM `ai_client.py` currently wraps."

### The contract, and what actually changed in `engine.py`
`ai_diagnose(facts)` used to return a bare `(reason_code, text)` tuple. It now returns a dict: `{reason_code, explanation, confidence, evidence, recommendation}` — `confidence`/`evidence`/`recommendation` are `None`/`[]` on the offline deterministic path (there's no confidence in a hand-written if-else), and only populated when the real model actually ran. The original deterministic logic was **not rewritten** — it was renamed to `_offline_diagnose()` unchanged, and is now used in two places: as `ai_diagnose()`'s own offline branch, and as `_llm_diagnose()`'s fallback when the real API call fails for any reason (auth, network, invalid `reason_code` in the response). `emit()` gained three new optional kwargs (`confidence`, `ai_evidence`, `ai_recommendation`, all defaulting to `None`/`[]`) purely to carry this through to the output DataFrame — no tier/matching/threshold logic changed at all. This required touching the one `ai_diagnose(...)` call site inside `reconcile()`'s Tier 3 branch, which is the exact, intentional seam this file's own docstring described from the start ("swapping in a real Claude/Gemini call means replacing the body below").

### `ai_client.py` — Gemini specifics
Uses Gemini's structured-JSON output mode (`generationConfig.responseMimeType: "application/json"` + `responseSchema`), not function-calling/tools — simpler for "just give me back one JSON object" than Anthropic's tool-use pattern would have been. Raw `requests` calls, no `google-generativeai` SDK, matching the project's established preference (see `razorpay_client.py`) for REST over vendor SDKs. Money fields are converted to `"Rs 1,234.56"`-style strings *only in the prompt text* (`_humanize_facts()`), never in the `facts` dict that reaches `engine.py`'s offline arithmetic — that dict must stay raw integer paise, because `_offline_diagnose()` does real arithmetic on it (`abs(delta) / amt * 100`, etc.) both as the normal offline path and as the LLM-failure fallback.

### Gotcha: Google deprecated the model mid-project, with only a runtime 404
`gemini-2.0-flash` returned a 404 with the message "This model ... is no longer available ... use models/gemini-3.6-flash". No build-time warning, no deprecation notice anywhere in the code — just a runtime failure the first time it was actually called. **When a hosted-model API call fails with a 404 naming the model, read the error body before assuming a code bug** — it may simply be naming its own replacement, as it did here.

### Gotcha: free-tier rate limits are real and will hit during normal testing
Burned through the Gemini free-tier quota during verification (self-test + a full-dataset regression run + a couple of UI-driven test batches, in fairly quick succession) and got a genuine `429` mid-session. **This was useful, not just annoying** — it proved the fallback-to-offline path (see above) actually works under a real failure, not just in a mocked test: the explanation text for the affected records came back prefixed `[AI unavailable -- Gemini returned 429: ...]` followed by the same trustworthy deterministic sentence, with `confidence`/`evidence`/`recommendation` correctly left `None`/`[]` rather than fabricated. For an actual judge demo: a 60-order batch only sends ~5-10 real calls (Tier 3 + Tier-4-MANUAL_REVIEW only), which should sit comfortably under most quotas — the risk is from repeated *testing* right before presenting, not from one real demo run.

### Verified live-call accuracy — and an honest tradeoff worth explaining if asked
Ran the full 180-record dataset with `RECONAI_LLM=1` (real calls, no mocking) end to end: tier/disposition accuracy stayed 100%, clearing-decision precision/recall stayed 100% (nothing wrongly auto-cleared, no human bothered for nothing) — but reason-code accuracy against the synthetic ground truth dropped to 99.45% (one record, `ORD-00034`, a `T3_OVERCHARGED_FEE` case, got classified `R4_PARTIAL_PAYMENT` by the live model instead of the ground truth's assumed `R5_AI_VARIANCE`). Both codes are valid, defensible reads of that specific ambiguous case — this is the honest, expected cost of a real thinking model replacing a hand-coded heuristic, not a bug, and it did not touch the money-safety numbers at all. Worth saying plainly if a judge asks "does your score still say 100%" — it doesn't, by design, once real AI judgment replaces a deterministic stand-in, and that's evidence the AI is doing real work rather than being wired to always agree with the test fixture.

### Current AI coverage — deliberately narrower than "Tier 3"
`ai_diagnose()` is called from exactly one branch in `reconcile()`: "matched, but the amount is wrong by more than the known fee band." That branch is reached by **both** Tier 3 (has a gateway ref) and Tier 4 (COD/bank, UTR-matched) when the shortfall is too large to be a normal fee — so real AI investigation already covers some Tier 4 cases too, not only Tier 3. **Tier 0 (COD timing) and Tier 5 (unmatched/ambiguous/orphan) get zero AI involvement today** — they go straight to their disposition with no model call. For Tier 0 and the no-settlement-at-all / overdue-timer flavors of Tier 5 that's correct (there's no real judgement to make). But two Tier 5 sub-cases are genuine, previously-identified-but-unbuilt AI candidates per this file's own 7-case taxonomy above: **ambiguous multi-candidate match** (case 3) and **orphan-settlement correlation** (case 2, the shadow-duplicate scenario) — both currently pure rule-based "flag it, human decides," with no attempt at AI-assisted correlation. Asked the user whether to extend AI there next; no answer yet as of this writing — check before assuming it's in scope.

**Superseded — see the session update below.** This entire section describes where the project stood right after the *first* live Gemini wire-up. Since then, the AI call moved out of `engine.py` entirely, ambiguous_match and unmatched_settlement (cases 2 and 3 above) both got wired to real AI, and the whole batching/caching/case-lifecycle layer described below was built on top. Treat this section as history of how the integration started, not the current architecture.

---

## Session Update (Aug 28-29, 2026): Batched AI + persistent case store (rate-limit-driven pivot), full UI redesign

### Why: the free-tier math didn't work
The previous session's one-call-per-flagged-record design hit Gemini's real free-tier ceiling (5 requests/min, 20/day — confirmed via the user's own Google AI Studio dashboard) almost immediately under normal testing. The user explicitly ruled out fixing this with billing ("no i am not gonna do billing") and instead specified the fix directly, in plain language, before any code was written: batch several cases per request, cache real results by an evidence fingerprint, and degrade honestly (never fabricate, never crash) when the quota is actually exhausted. Built exactly to that spec after an explicit discuss-first round (**"wait dont start building now, i want you to discuss first"** — a real correction to slow down that should be treated as a durable preference for any future big architecture change, not just this one).

### `engine.py` is now 100% network-free again
`ai_diagnose()` always returns the offline `_offline_diagnose()` heuristic. The real AI call moved entirely to a new module, **`case_engine.py`**, which runs once per batch, strictly after `reconcile()` finishes. Do not add a live AI call back into `engine.py` — the seam is deliberately one level up now.

### `case_engine.py` — the real AI layer, in one place
- `_AI_ELIGIBLE_TYPES = ("partial_payment", "overpayment", "ambiguous_match", "unmatched_settlement", "unmatched_order", "remittance_overdue")`. Excludes `pending_settlement` (normal COD window, nothing to investigate) and anything cleanly auto-matched (never becomes a case).
- `investigate_new_cases_batched()` chunks eligible cases into groups of `ai_client.DEFAULT_BATCH_SIZE` (5) and sends each chunk as **one** Gemini request via `ai_client.investigate_batch()` — a structured-JSON response keyed back to `case_id`. This is the direct fix for the RPM/RPD ceiling: it caps request count, not case count.
- `_evidence_hash()` — SHA256 fingerprint of the facts that matter to a case (type, expected/received/delta, candidate IDs, reason). `build_cases_for_batch()` reuses a case's stored AI result when the hash is unchanged from its last real investigation, and only queues a fresh Gemini call when it changed. **Never call Gemini merely because Streamlit rerun happened or a ticket was opened** — this cache is what guarantees that.
- **`ai_pending`** is a fourth case-lifecycle state, distinct from `manual_review`: it means AI hasn't had a chance to look yet (usually a 429), not that AI looked and recommends a human decide. On `AIRateLimitError`, `investigate_new_cases_batched()` marks the whole current chunk **and all remaining un-attempted chunks** `ai_pending` and stops immediately — no retry loop, no blocking sleep. A user-triggered retry (`retry_pending_cases()`) is the only way an `ai_pending` case gets re-attempted.
- `AUTO_RESOLVE_CONFIDENCE_FLOOR = 85` — an AI `resolve` action below this confidence is downgraded to `manual_review` in code, not just by prompt instruction. This is the same "never auto-clear without justification" rule as the rest of the project, enforced structurally.
- `_status_from_ai_action()`: `resolve → ai_recommendation`, `manual_review → manual_review`, `escalate → exception`. `exception` is its own status now, distinct from `manual_review` — it means AI found *nothing* to weigh (no candidates, no evidence) versus `manual_review` meaning AI found real evidence but couldn't resolve unambiguously.
- `investigate_case_followup()` / `fetch_missing_evidence()` — the one controlled agentic step. When Gemini names specific `missing_evidence`, a user-triggered "Investigate Further" fetches what's realistically fetchable (today: a customer's other order history — the only real evidence source beyond the CSVs) and makes exactly **one** more Gemini call. Never automatic, never looped further. `build_case_context()` and `apply_ai_result()` are public (not underscore-prefixed) specifically so `app_new.py`'s ticket page can call them individually to drive a real step-by-step progress UI — don't re-privatize these without checking that call site first.
- `try_direct_answer()` — Ask AI answers common questions (case ID lookup, "which orders are pending", "how much is outstanding", "which cases are AI-pending") straight from the case store via pandas, zero API cost, returning `None` (falls through to a real `ai_client.ask()` call) only for genuinely novel questions.

### Dataset resized again: 2 batches of 50, not 3 of 60
`gen_data.py`'s `PLAN` now totals exactly 100 records, split into `N_BATCHES = 2` of `BATCH_SIZE = 50` each (plus a couple of hand-built special cases per batch — bulk-COD orders, orphan-credit settlements, one shadow-duplicate settlement — so actual on-disk counts run ~52/batch, 104 orders / 95 settlements total). Reasoning: the buildathon only requires demonstrating 50+ records through the agent; a third batch added demo runtime without adding required coverage. Re-validated after resizing: 100% tier/disposition accuracy and 100% clearing precision/recall against `ground_truth.csv`. **`state_store.TOTAL_BATCHES = 2`** — if this project ever needs a 3rd batch again, that constant and `gen_data.py`'s `N_BATCHES` both need updating together, plus re-validating against `ground_truth.csv`.

### The case model (`state_store.py`)
Every non-clean record becomes a **case** (`state_store.py`'s `cases` dict, keyed by `case_id`), persisted per-merchant, surviving reruns/refresh/logout. `case_status` values: `pending_settlement`, `needs_ai`, `ai_pending`, `ai_recommendation`, `manual_review`, `exception`, `resolved`. New this session: `bookmarked` (bool, toggled via `state_store.toggle_bookmark()`) and `comment` (string, set via `state_store.set_comment()` or frozen into `resolution.comment` at resolve time) — both preserved across `upsert_case()` re-evaluation the same way `resolution`/`history`/`created_at` already were; don't forget this if either field's handling is ever touched, or a bookmark/comment will silently vanish the next time a cross-batch case gets re-upserted.

### Reconciliations page: funnel + awaiting-settlement widget, not a donut
Rebuilt to match the user's own reference mockups through several rounds of direct screenshot feedback. Key pieces: 4 KPI cards (no fabricated "vs last month" trend — explicitly rejected when discussed), a **Reconciliation Resolution Funnel** (stacked bars, replacing the old CSS-gradient donut, which was removed as dead code) with a conditional "AI Pending" row shown only when nonzero, an **Awaiting Settlement** widget (`pending_settlement` cases pulled *out* of the Review Queue entirely — the user's own framing: "they are not there for getting reviewed"), and a **Review Queue** with 5 real filter pills sorted by AI confidence descending.

### The AI Investigation Ticket — redesigned twice; first pass was too dense
First redesign packed 8 cards + tabs + 2 callout boxes onto one page. User called this out directly and supplied a leaner reference mockup. Current design (in `app_new.py`'s `_render_case_ticket()`):
- **Three flat columns**: Case Summary (money + order/settlement metadata together) | AI Analysis (Finding → Evidence → Recommendation as one narrative, not three cards) | Supporting Documents (popover chips — Order Details, Settlement Details, Fee Structure/MDR, Candidate Matches, Activity Log — each rendered **only when the underlying data actually exists** for that case; never an empty placeholder chip).
- Fee Structure (MDR) chip computes the real tolerance band via `config.fee_band()` — the same constants `engine.py` itself uses at Tier 2 — not a fabricated reference table.
- **Bookmark** (top-right) replaces an "Actions ▾" dropdown per explicit user preference.
- **Comments rule, asymmetric on purpose**: Accept & Reconcile auto-fills the comment from AI's real `next_step` (still editable); Keep for Manual Review is **blocked** until a comment is typed (verified via `AppTest` — the block correctly refuses to resolve and shows an inline warning). The comment box is a collapsed `st.expander` by default and auto-opens only when that block fires — per the user's own instruction to keep it "less prominent... it only needs to become important when manually resolving."
- **Investigate Further** shows real 4-step progress (Identifying → Retrieving → Analyzing → Updating), each tied to an actual function call completing via the newly-public `case_engine.build_case_context()`/`apply_ai_result()` — reuses the same `_render_steps()` placeholder-redraw technique as the batch sync flow, now generalized to accept any `steps` list. Not a cosmetic delay.
- Button order/emphasis, per explicit final feedback: **Accept & Reconcile** (renamed from "Accept Recommendation" — the user's own reasoning: "more explicit for a beginner user" since it actually changes reconciliation state) is primary/leftmost; Investigate Further stays secondary/purple-outline; Keep for Manual Review stays neutral/rightmost.

### Gotcha found and fixed: `!important` CSS can hide Streamlit's real `:disabled` state
Disabled action buttons (e.g. Accept & Reconcile when AI recommended `escalate`, not `resolve`) still rendered with full color and looked fully clickable, because the button styling used `background: {COLOR} !important` with no `:disabled` variant — Streamlit's native dimmed-disabled look was fully overridden. The underlying enable/disable logic was already correct (confirmed via `AppTest`'s `.disabled` property); only the visual signal lied. **Rule going forward: any button styled with `!important` color/background overrides needs an explicit `button:disabled` rule too**, or a genuinely disabled button will look clickable. Caught by the user from a live screenshot, not by testing — a reminder that `AppTest` confirms *logical* state but not visual rendering; a real screenshot is still the only way to catch a CSS-only bug like this.

### Honest list of what's NOT done (check before claiming otherwise in a demo)
1. **COD bulk remittance (one UTR covering many orders) is still not modeled** — `engine.py`'s `by_utr` stays strictly 1:1. Flagged as a genuine architectural gap since this file's original 7-case taxonomy (case 5); still unbuilt. Needs explicit discussion before touching, same as this file's standing rule for any engine change.
2. **Risk Summary widget on the Reconciliations page still reads the old per-run `flagged_records` snapshot**, not the new case store the rest of the page uses. Not wrong, just inconsistent with everything else on that page now.
3. **The live "Investigate Further" Gemini call has never been observed succeeding end-to-end** — every real attempt during development hit the rate limit first. The orchestration was verified correct with the network call mocked; the actual live path is untested by direct observation.
4. **`RECONAI_LLM=1` is still a dead line in `.env` and `.env.example`** — nothing reads it any more since `engine.py` stopped taking an AI env toggle. Harmless, but should be deleted.
5. Sidebar stub pages (Transactions, Reports, Data Sources, Settings) remain "coming soon" — never scoped as buildathon deliverables.