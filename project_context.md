# Ledgr — Project Context

## 1. Project Overview

Ledgr is a financial/payment reconciliation platform being built for the Razorpay Buildathon.

The core purpose is to reconcile payment/order records with settlement records and identify discrepancies that require investigation.

The project should demonstrate:
- deterministic financial reconciliation
- clear explanations for mismatches
- handling of ambiguous cases
- human review when automation is not sufficiently certain
- AI-assisted forensic investigation
- potential Razorpay API integration

---

## 2. Existing Project

> **⚠ SUPERSEDED — see Section 23.** This file list describes the Streamlit era.
> `app.py`, `app_new.py`, `login.py` and `theme.py` no longer exist (deleted in
> commit `e587a0b`). The UI is now React in `frontend/`, served by `api.py`
> (FastAPI). Everything below about `engine.py`, `case_engine.py`,
> `state_store.py`, `config.py` and the data files is still accurate.

Current important files include:

- `app_new.py` — **the live application** (sidebar + header shell, page-routed: Dashboard, Reconciliations, AI Review, Exceptions, etc.). `app.py` is an earlier prototype, kept for reference only — not the active entrypoint.
- `login.py` — login screen (split-panel design, demo-account cards); writes `?m=<email>` to `st.query_params` on success so a browser refresh doesn't bounce back to login.
- `auth.py` — `DEMO_MERCHANTS`, `authenticate()`, `get_merchant_by_email()` (password-free lookup used only to restore a session from the query param, never to log in).
- `theme.py` — shared colors/fonts/CSS helper (`html()`, `base_css()`) used by every screen.
- `state_store.py` — per-merchant persisted JSON (`data/state/<merchant_id>.json`): batch progress, notification lifecycle, saved reconciliation runs (each with its own individual flagged records).
- `engine.py` — core reconciliation engine and matching logic (5-tier waterfall). Also now owns the real `ai_diagnose()`/`_llm_diagnose()` call into `ai_client.py`.
- `ai_client.py` — isolated Gemini (Google AI) REST client, same architectural pattern as `razorpay_client.py`. See Section 21.
- `razorpay_client.py` — real, isolated Razorpay settlements client (raw REST, no SDK).
- `shopify_client.py` — mock Shopify orders client (honestly labeled as demo data, never claims a live connection).
- `config.py` — configuration and thresholds (money-as-paise helpers, fee bands, `REASON_LEGEND`, `TIER_NAMES`, `priority_of`).
- `gen_data.py` — demo/test data generation. Currently targets ~180 total orders across 3 batches of 60 (see Section 20) — NOT the original 900-1000.
- `validate_data.py` — data validation (cross-checks `ground_truth.csv` against `orders.csv`/`settlements.csv`/`config.py`).
- `schema_map.py` — schema/field mapping.
- `customers.csv` — customer/order-related data.
- `review_log.csv` — review/audit information.
- `data/` — project data (`orders.csv`, `settlements.csv`, `ground_truth.csv`, `run_results.csv`, `state/` per-merchant JSON).
- `.env` / `.env.example` — Razorpay + Gemini API keys, `RECONAI_LLM` toggle. `.env` is gitignored.
- `.streamlit/` — Streamlit configuration.

The existing codebase must be inspected and understood before making architectural or implementation changes.

---

## 3. Core Reconciliation Engine

Ledgr uses a 5-tier waterfall reconciliation approach.

The reconciliation engine is deterministic.

Important rule:

DO NOT casually rewrite `reconcile()`.

DO NOT change existing matching rules or tier definitions unless explicitly discussed and approved.

The existing deterministic engine should remain the source of truth for reconciliation.

AI should augment the system rather than replace the core reconciliation engine.

---

## 4. AI Forensic Agent

A major planned feature is an AI Forensic Agent.

The purpose of the AI agent is NOT simply to look at a numerical mismatch and guess an explanation.

Instead, when a transaction is flagged, the AI should investigate the available evidence and determine what most likely caused the discrepancy.

Potential evidence can include:

- order information
- settlement information
- payment events
- refunds
- disputes
- fees
- settlement batches
- payment status
- historical patterns
- Razorpay API information
- other transaction-related evidence available to the system

The AI should produce an explanation grounded in evidence.

The desired workflow is approximately:

1. Reconciliation engine processes records.
2. Normal deterministic matches are accepted.
3. Suspicious/flagged cases are identified.
4. Relevant evidence is gathered.
5. AI forensic analysis examines the evidence.
6. AI produces a structured diagnosis.
7. The system records the evidence/reasoning.
8. High-confidence cases can receive a useful automated explanation.
9. Ambiguous or unsafe cases go to human review.

The AI must not invent evidence.

If required evidence is unavailable, the AI should say that it is unavailable rather than hallucinating a conclusion.

---

## 5. Human Review / Pending Review

The project includes a Pending Review workflow.

This is important for cases where the system cannot safely determine the correct result.

Examples include:

- multiple possible matches
- ambiguous transactions
- insufficient evidence
- conflicting evidence
- unusual financial discrepancies

The system should allow a human to review these cases and approve/reject or otherwise resolve them.

The AI should assist the reviewer rather than remove the reviewer from the loop.

---

## 6. Ambiguous Cases

One important edge case discussed previously is multiple possible matches.

For example, two records may appear to correspond to the same customer/name or otherwise create ambiguity.

The system should not blindly select one.

Instead:

- detect ambiguity
- preserve the possible candidates
- explain why the case is ambiguous
- route it to Pending Review when necessary
- allow a human to make the final decision

A key principle is:

> Exceptions should be handled safely rather than forcing an incorrect automated match.

---

## 7. AI Forensic Investigation Philosophy

The AI feature should feel like an actual forensic investigation rather than a chatbot.

For a flagged case, the agent should ideally answer:

- What happened?
- What evidence supports that conclusion?
- What financial variance exists?
- What events could explain it?
- Which evidence was checked?
- What evidence was unavailable?
- How confident is the diagnosis?
- Does this require human review?

The final output should be structured and auditable.

---

## 8. Razorpay Integration

Razorpay API integration is part of the broader project direction.

The AI forensic workflow may use Razorpay data as evidence when available.

The implementation should first determine:
- what Razorpay APIs/data are actually available
- what credentials/configuration are required
- what evidence can realistically be retrieved
- how API failures should be handled
- how API data should be incorporated without breaking deterministic reconciliation

Do not assume an API endpoint or field exists without verifying it.

---

## 9. Important Architectural Principle

Separate responsibilities:

### Deterministic engine
Responsible for:
- matching
- reconciliation
- tier logic
- financial calculations
- deterministic classification

### AI forensic layer
Responsible for:
- investigating flagged cases
- interpreting available evidence
- identifying likely causes
- generating structured explanations
- identifying uncertainty
- recommending human review when appropriate

### Human review layer
Responsible for:
- resolving genuinely ambiguous cases
- approving/rejecting uncertain decisions
- providing final authority for exceptions

The AI must not silently override deterministic financial logic.

---

## 10. Development Rules

Before changing code:

1. Inspect the complete existing codebase.
2. Understand the current architecture.
3. Understand the current reconciliation flow.
4. Understand the current Pending Review flow.
5. Identify existing AI-related/stub code.
6. Identify what is already implemented.
7. Identify what is missing.
8. Propose an architecture before making major changes.
9. Explain the proposed changes.
10. Wait for approval before making significant architectural changes.

Do not rewrite working components simply to make the architecture look cleaner.

Prefer small, isolated changes.

Preserve existing behavior unless a change is explicitly required.

---

## 11. Current Goal

The immediate goal is to properly design and implement the AI Forensic Agent while preserving the existing reconciliation system.

The project should eventually demonstrate a convincing end-to-end flow:

Data
→ Deterministic reconciliation
→ Flagged case
→ Evidence collection
→ AI forensic investigation
→ Structured diagnosis
→ Confidence/evidence
→ Automated explanation OR Pending Review
→ Human decision when required

---

## 12. Buildathon Goal

This project is intended for the Razorpay Buildathon.

The AI component should therefore solve a real financial/reconciliation problem rather than being an AI feature added only for demonstration.

The final system should be explainable enough that the builder can confidently explain:

- why AI is needed
- why deterministic rules alone are insufficient
- how the AI obtains evidence
- how hallucinations are controlled
- how ambiguity is handled
- how humans remain in control
- how Razorpay data can be incorporated
- why the architecture is safe for financial reconciliation

---

## 13. Working Style

The developer wants to understand the implementation.

When explaining technical concepts:
- use simple language
- avoid unnecessary jargon
- explain why a change is needed
- explain how it fits into the existing system
- do not blindly generate large amounts of code without first explaining the approach

The architecture should be developed step-by-step.

---

## 14. Current Status

This file is being created as a persistent backup of the project's context.

The next step is NOT to immediately rewrite the project.

First:
- inspect the existing codebase
- reconstruct the current architecture
- verify what has already been implemented
- identify the exact insertion point for the AI forensic workflow
- then agree on the implementation plan

---

## 15. AI Implementation Architecture (Updated Aug 26, 2026)

### Core Principle: Hybrid Approach

The AI agent does NOT replace the deterministic engine.

**Architecture layers:**
1. Deterministic engine (engine.py) - handles 85-90% via Tiers 0-2
2. AI Forensic Agent (new) - investigates remaining 10-15% (Tier 3)
3. Human review - final authority on ambiguous cases

### When AI is Used vs Not Used

**DO NOT use AI for (Tier 0-2):**
- Exact amount matches
- Known fee deductions within tolerance (2-3%)
- Direct UTR/gateway_ref matches
- COD within collection window (0-14 days)

**USE AI for (Tier 3):**
- Amount variance outside fee tolerance
- Unknown/complex deduction patterns
- Ambiguous matches (multiple candidates)
- Cases requiring multi-step reasoning
- Generating human-readable explanations

**AI Technology Choice:**
- Using: LLM (Claude API) for reasoning + explanation
- NOT using: Traditional ML (needs training data)
- NOT using: Full agentic AI (too complex for scope)
- Optional: Light agentic features (AI plans, human executes)

### Real-World Data Challenges

**DO NOT assume perfect data quality:**

COD reconciliation reality:
- Only 20% have perfect courier reports with order IDs
- 80% have bulk remittances (1 UTR for multiple orders)
- Courier reports often missing, incomplete, or wrong format
- Multiple couriers = multiple incompatible formats
- bank_utr not always present (bulk payments, system lag)

Online payment reality:
- Razorpay API sometimes has lag (24-48h for chargebacks)
- Customers can change payment method at checkout
- Gateway fees vary (international cards, special categories)
- Refunds/disputes not always immediately visible

**The AI layer exists specifically to handle these imperfect data scenarios.**

### Customer History as Secondary Evidence

Customer history is NOT primary matching criteria.

**Primary matching:** UTR, gateway_ref, amount
**Secondary (AI uses):** Customer payment history, behavior patterns

**Valid uses:**
1. Breaking ties in ambiguous matches (2 customers same name)
2. Fraud risk assessment (new customer with large order)
3. Behavior pattern validation (customer switched payment methods)
4. Trust scoring (100% payment history vs 0%)

**Invalid uses:**
- ❌ Matching by name alone without amount/date/mode
- ❌ Auto-clearing based only on good history
- ❌ Ignoring actual transaction data

### Confidence-Based Routing

AI must provide confidence scores with every diagnosis:

**90-100%:** Auto-clear (with full evidence and explanation)
- Example: International card verified via API, fee matches exactly 5%

**70-89%:** Suggest match but flag for review
- Example: Ambiguous match, strong evidence for one candidate

**40-69%:** Present options, require human decision
- Example: Multiple plausible explanations, incomplete evidence

**0-39%:** Flag as needs investigation
- Example: No matching candidates or conflicting evidence

**Always err on side of caution for financial data.**

### Razorpay API Integration

API is for evidence collection, not primary matching.

**What API provides:**
- Payment status, actual fee charged
- Card type (international/domestic)
- Refunds, disputes, chargebacks
- Payment method details

**How used:**
1. Tier 3 variance → Call API automatically
2. AI analyzes: order + settlement + API data
3. Generate explanation with evidence
4. Route based on confidence

**If API fails:**
- Never auto-clear
- Flag: "Could not verify (API unavailable)"
- Provide manual review option

### Implementation Phases

**Phase 1 (MVP for buildathon):**
- Replace `_llm_diagnose()` stub with Claude API
- Evidence collector (CSV data + optional Razorpay API)
- Structured output: reason, confidence, evidence, actions
- Confidence-based routing

**Phase 2 (UI):**
- Show AI investigations in dashboard
- "AI Auto-Cleared" separate category
- Evidence panels (what checked, what found)
- Draft messages (emails to stakeholders)

**Phase 3 (Optional):**
- Pattern detection (systematic courier delays, etc.)
- Bulk actions (approve multiple AI suggestions)
- Light agentic features

### Buildathon Value Proposition

**Focus on:**
"AI explains payment variances that deterministic rules cannot handle, reducing manual investigation from 2-3 hours to 15-20 minutes per batch."

**Demo scenarios:**
1. International card - AI verifies 5% MDR via API, auto-clears
2. Large unknown variance - AI investigates, drafts escalation email
3. Ambiguous COD match - AI weighs evidence, suggests match with confidence
4. Pattern detection - AI notices systematic gateway overcharging

**NOT claiming:**
- AI matches all payments (false - deterministic handles 90%)
- AI replaces engine (false - augments only)
- AI works on perfect data (false - handles messy data)

### Known Issues and Loopholes Addressed

**Issue 1:** "Why not just match by UTR for COD?"
- Answer: We do when available (primary method)
- AI only needed when UTR missing (bulk remittances, system lag)

**Issue 2:** "Delivery guy knows amount, why mismatch?"
- Answer: Real problems - customer complaints, doorstep returns, courier penalties, cash errors
- AI helps investigate these edge cases

**Issue 3:** "Don't couriers send order lists?"
- Answer: Only 20% of merchants get clean reports
- 80% deal with bulk payments, missing reports, format mismatches
- AI bridges the gap

### Critical Rules for AI Implementation

1. **Never auto-clear without justification**
   - Confidence alone insufficient
   - Must have: complete evidence + low risk + validated pattern

2. **Never invent evidence**
   - If API unavailable, state that
   - If data missing, acknowledge gap
   - Uncertainty is acceptable, fabrication is not

3. **Preserve human authority**
   - Ambiguous cases → human decides
   - High-risk cases → human approves
   - AI assists, doesn't replace judgment

4. **Be conservative**
   - When in doubt, flag for review
   - Financial accuracy > automation rate
   - Under-promise, over-deliver on confidence

---

## 16. Session Notes (Aug 26, 2026)

**Key learnings from user discussion:**
- User has strong understanding of ideal COD flow (UTR matching)
- User correctly identified loopholes in oversimplified examples
- User wants AI for real problems (messy data), not perfect scenarios
- Focus shifted from "AI matches everything" to "AI handles edge cases"

**Architectural clarity achieved:**
- Hybrid approach (if-else + LLM + human) fully defined
- When AI is needed vs not needed clearly documented
- Real-world data quality challenges acknowledged
- Customer history usage scoped correctly (secondary, not primary)

---

## 17. Major Architecture Shift: CSV Tool → SaaS Platform (Aug 26, 2026)

### New Vision

Transform Ledgr from a **CSV upload tool** to a **multi-tenant SaaS platform** with auto-sync capabilities.

### Core Changes

**From:**
```
User uploads orders.csv + settlements.csv → Reconciliation → Results
```

**To:**
```
Merchant logs in → Auto-sync from APIs → Reconciliation → Dashboard
```

### Key Features

1. **Authentication Layer**
   - Company-specific login (3-4 demo accounts for buildathon)
   - Session management
   - Multi-tenancy (each merchant sees only their data)

2. **Auto-Fetch Orders**
   - From merchant's e-commerce platform
   - Target: Shopify, WooCommerce, custom APIs
   - **Buildathon scope:** Mock Shopify API with realistic demo data

3. **Auto-Fetch Settlements**
   - From Razorpay API (REAL integration)
   - Uses merchant's Razorpay API keys
   - Razorpay naturally isolates data by API key

4. **Incremental Sync Strategy**
   - Store `last_sync_timestamp` per merchant
   - Fetch only NEW records: `created_after=last_sync_timestamp`
   - Prevents re-fetching entire dataset
   - **Example:**
     ```python
     # Only fetch orders created after last sync
     GET /api/orders?created_after=2026-08-26T10:30:00Z
     
     # Razorpay settlements from timestamp
     GET /v1/settlements?from=1724665800
     ```

5. **Multi-Merchant Data Isolation**
   - Each merchant has separate Razorpay API credentials
   - Filter e-commerce orders by `payment_gateway_names = ["razorpay"]`
   - Prevents cross-merchant data leakage

### Critical User Questions Addressed

**Q1: Won't the system re-fetch all orders every time?**
- A: No. Timestamp-based filtering ensures only NEW orders are fetched.
- Stored per merchant: `last_order_sync_at`, `last_settlement_sync_at`

**Q2: How to ensure orders belong to correct merchant when multiple merchants use same platform?**
- A: Match by `gateway_ref_id` (Razorpay payment ID)
- Each merchant's Razorpay API key only returns THEIR settlements
- Filter e-commerce orders to only those paid via Razorpay

**Q3: What if merchant uses multiple payment gateways?**
- A: Filter orders by `payment_gateway_names` field
- Only process orders where `"razorpay" in payment_gateway_names`
- Ignore Stripe/PayPal/COD orders (out of scope for Razorpay buildathon)

### Implementation Strategy (10 Days)

**What to build (REAL):**
1. ✅ **Simple login** - Hardcode 3-4 demo accounts (no OAuth/SSO)
2. ✅ **Real Razorpay API** - Fetch settlements + payment details (test mode)
3. ✅ **Mock merchant API** - Pre-prepared realistic Shopify-format JSON
4. ✅ **Settings page** - Show integration status, API key config
5. ✅ **Auto-sync dashboard** - "Sync Now" button with progress indicators
6. ✅ **Keep engine.py untouched** - Existing reconciliation logic stays
7. ✅ **CSV upload backup** - Safety net for demo

**What NOT to build (too complex):**
- ❌ Real OAuth SSO (Google/Microsoft)
- ❌ Real Shopify/WooCommerce API integration
- ❌ Database with encrypted credentials
- ❌ Webhook infrastructure
- ❌ Multi-gateway support

### Timeline (10 Days)

- **Day 1-2:** Login screen + session management
- **Day 3-4:** Real Razorpay API integration (test mode)
- **Day 5:** Mock merchant API with realistic demo data
- **Day 6:** Settings page (integrations UI)
- **Day 7:** Auto-sync dashboard
- **Day 8-9:** AI Forensic Agent (Claude API)
- **Day 10:** Polish + demo prep

### Demo Flow

1. **Login:** `demo@acmecorp.com` / `demo123`
2. **Dashboard:** Shows connected integrations (Razorpay ✓, Shopify ✓)
3. **Sync Now:** 
   - "Fetching orders from Shopify..." (mock)
   - "Fetching settlements from Razorpay..." (REAL API call!)
   - Progress bar
4. **Reconciliation:** Runs automatically on synced data
5. **Results:** AI-powered dashboard with investigations
6. **Backup:** Manual CSV upload tab still available

### What to Say During Demo

**✅ Say (honest):**
- "Auto-syncs with Razorpay via their API" (real!)
- "Supports Shopify, WooCommerce, custom APIs" (architecture does)
- "AI investigates variances using Razorpay payment data" (real!)
- "For demo, pre-integrated with test merchant store" (transparent)

**❌ Don't say:**
- "Fully production-ready" (it's an MVP)
- "Supports all e-commerce platforms" (only mocked one)
- "Enterprise SSO" (hardcoded logins)

### Technical Debt Acknowledged

For buildathon scope, acceptable shortcuts:
- Hardcoded credentials (no database encryption)
- Mock e-commerce API (not real Shopify integration)
- Simple login (no OAuth)
- No webhook infrastructure
- Single payment gateway (Razorpay only)

Post-buildathon priorities:
- Real database with encrypted credentials
- OAuth/SSO integration
- Real Shopify/WooCommerce connectors
- Webhook-based real-time sync
- Multi-gateway support

### Architecture Validation

User concerns addressed:
- ✅ Incremental sync prevents re-fetching (timestamp filtering)
- ✅ Multi-merchant isolation works (Razorpay API keys + gateway filtering)
- ✅ Data belongs to correct merchant (match by gateway_ref_id)
- ✅ Timeline is realistic (10 days, hybrid real/mock approach)

**User confidence level:** Initially nervous ("haven't built anything like this before")
**Our response:** Architecture is solid, timeline is achievable with smart scoping

---

## 18. Session Log: Login Built, Razorpay Client Verified Live, AI Case Taxonomy Defined (Aug 26-27, 2026)

### What got built and verified

- **Login/dashboard shell** (`login.py`, `app_new.py`, `auth.py`, new `theme.py`) — working, restyled to match `app.py`'s actual brand (not the purple-gradient theme an earlier pass invented), several real Streamlit rendering bugs found and fixed along the way (see `CLAUDE.md` for the technical detail — split-div wrapping, Markdown code-block misfires on multi-line HTML).
- **`razorpay_client.py`** — real, isolated Razorpay API client (settlements only, never orders). **Tested live against the user's actual Razorpay Test Mode credentials: authentication succeeded, 0 settlements returned.** This is the correct, expected result — confirmed via Razorpay's own docs that Test Mode never generates real settlements (no real money moves). Not a bug, not blocked — this is exactly the "Connected, but no live settlements" state the dashboard now shows honestly.
- **Dashboard wiring** — real connection status card (genuine API call, cached 30s), `data/settlements.csv` shown as clearly-labeled demo data underneath, "Sync Now" forces a fresh live check. Fake hardcoded status badges were replaced with the real result everywhere they appeared.

### Major clarification: three data sources, not two

Earlier sections of this file conflated "Razorpay integration" with "auto-fetch orders and settlements" as one thing. Corrected understanding, reached through direct questioning from the user:

1. **Orders** — always the merchant's e-commerce platform (Shopify, mocked for the buildathon). Razorpay's own Orders API is explicitly *not* used for this, even though it exists — keeping the boundary clean (Razorpay = payment/settlement data only) matters for the "why call Razorpay at all" pitch below.
2. **Online settlements** — Razorpay API, real, built, verified live.
3. **COD/bank settlement data** — a genuinely separate third source. **Razorpay has zero visibility into COD** — the customer pays the delivery agent in cash, and the courier remits it to the merchant's bank directly, completely bypassing Razorpay. This isn't a buildathon shortcut to fix later; getting this "for real" means a regulated bank Account Aggregator integration or direct per-courier remittance APIs, both explicitly out of scope. For now and for the foreseeable future, this stays either synthetic (`gen_data.py`'s `BANK`-sourced rows in `settlements.csv`) or manual upload — the same mechanism `app.py`'s original CSV flow already provides. The existing `settlements.csv` already unifies both origins via its `source` column (`RAZORPAY` vs `BANK`) — real Razorpay settlements should be *merged* into this file at sync time, not replace it.

### Major clarification: sync is incremental, reconciliation is not

`engine.reconcile()` has no memory — every call is a full, stateless join over whatever DataFrames it's given. Discussed at length with the user via a concrete 3-day walkthrough (Monday: order fetched, no settlement yet; Tuesday: an unrelated orphan settlement arrives and gets human-resolved; Wednesday: Monday's order finally gets its real settlement). The conclusion: **fetching can and should be incremental** (don't re-download what's already stored, using `last_sync_at` timestamps), **but reconciliation must always run against the full cumulative dataset**, because a match can legitimately span across sync batches days apart. Reconciling only "today's new fetch" in isolation would turn normal settlement lag into false-positive orphan exceptions.

Previously-flagged, still-unresolved exceptions will naturally reappear on every rerun — expected behavior, not a bug — because nothing is ever deleted from the underlying data. `review_log.csv` (pre-existing, append-only: `record_id,resolved_at,note`) is the mechanism that suppresses already-resolved records from the "needs attention" view. **Retention policy agreed:** unresolved records are kept indefinitely; for resolved duplicate-payment cases specifically, keep a permanent lightweight audit record (same shape `review_log.csv` already has) forever, but the full investigation evidence can be pruned after 7 days — never delete the fact that something was flagged and how it was resolved, since a chargeback dispute weeks later would need exactly that proof.

A future "open items ledger" optimization (archive terminal/closed records out of the working set so reconciliation cost doesn't grow with total historical volume forever) was discussed and explicitly deferred — not needed at demo data volumes, worth designing for once this is more than a demo.

### The AI Forensic Agent: sharpened into 7 concrete, code-grounded cases

Earlier phases of this project described AI's role in fairly abstract terms ("ambiguous matching," "unknown variance"). This session forced much sharper grounding by repeatedly asking "why would this actually happen" and "isn't this just a lookup" for every proposed case — and caught a real mistake along the way: an early example used "settlement amount exactly matches a known refund" as an AI use case, when that's explicitly listed in this very file (Section 15) as a case that does *not* need AI — it's a plain data lookup once you have the recon evidence. That correction produced the operating principle now in `CLAUDE.md`: **AI only earns its place where a deterministic lookup structurally cannot answer the question** — and Tier 3 should split into a deterministic 3a (check the evidence table first) and a real-AI 3b (only what's left over).

The seven cases (full detail, with `engine.py` line references, now lives in `CLAUDE.md` under "AI Forensic Agent — the 7-case taxonomy" — not duplicated here to avoid drift):
1. Genuine unexplained variance — already has a code stub (`ai_diagnose`/`_llm_diagnose`), not yet wired to a real model.
2. Duplicate/overpayment — corrected understanding: this shows up as an *orphan settlement* (Tier 5), not a same-order double-amount case, because a single `payment_id` can't be captured twice and Razorpay's own duplicate-payment guard protects same-order retries. The real mechanism: a failed confirmation causes a checkout retry that creates a *second* Razorpay order, evading that guard.
3. Ambiguous multi-candidate match.
4. Order with zero matching settlement — mostly a lookup (check live payment status), not real reasoning.
5. COD bulk remittance split — genuinely not modeled in `engine.py` today (`by_utr` is strictly 1:1); this is the one case requiring an actual engine change, which needs explicit user sign-off before touching per this project's own rules.
6. Free-text/inconsistent courier bank narration parsing.
7. Human-facing text generation (escalation emails, refund recommendation drafts) — zero financial-decision risk, since a human reviews and sends.

**Hard rule reaffirmed, stronger than the general confidence table in Section 15:** even at high AI confidence, anything that moves money (executing a refund) requires human approval. AI's job stops at producing the evidence-backed recommendation.

### Two real schema gaps found (not yet fixed)
- `orders.csv`/`ORDER_OPTIONAL` has no customer phone/email — limits how confidently an orphan settlement or ambiguous match can be correlated to a customer beyond amount/date proximity.
- No courier/delivery-partner field anywhere in the order schema — Case 7's escalation email has no addressee today. Partially resolved in design: Shopify's Fulfillment API has a `tracking_company` field (confirmed, includes DTDC) that will solve this once real Shopify order fetching exists — but it's not in the current mock schema yet.

### Why call real APIs at all — sharpened for the demo pitch

The user raised a sharp, important concern: does calling Razorpay's and Shopify's APIs actually look meaningful to judges, or just decorative? Verified rather than assumed: payment reconciliation via live API is a real, established SaaS category (Airwallex, Payrails, Taxilla, etc., all market themselves against "legacy manual CSV" tools). But the honest breakdown: the bulk settlement fetch is useful automation but **table-stakes** — every competitor in that space claims it. The genuinely differentiated, hard-to-replicate value is the **Tier-3 payment-fetch evidence call** — live, on-demand detail on one specific flagged transaction (refund status, dispute status, card type) that a static CSV export can never contain. **The demo narrative should tie the API integration directly to the AI agent's evidence-gathering, not present it as "we automated a file upload."**

---

## 19. Session Log: Dashboard Redesign as HTML Shell + Minimal Widgets (Aug 27, 2026)

Rebuilt the post-login dashboard (`app_new.py`) into the command-center layout the user specified: header (Ledgr wordmark, centered merchant org name, icon-only avatar with a Profile/Settings/Log out dropdown), three source-status cards (Orders/Settlements/COD-Bank, each tagged with a small colored dot + provider name), a "Last Reconciliation" block, a centered Sync & Reconcile CTA, and an honest empty-state activity log.

Getting the layout genuinely precise (not just visually close) took several real rounds — full technical detail (exact CSS, testid names, positioning technique) now lives in `CLAUDE.md` under "Dashboard rebuilt as HTML shell + minimal widgets," not duplicated here. The short version: repeated attempts to override a Streamlit container's own layout behavior (`display`, `position`) via custom CSS classes kept losing against Streamlit's own styling — the fix was to stop fighting that battle entirely: use `st.columns()` for actual placement (reliable every time), and restrict custom CSS to visual details only (colors, radius, padding on the innermost elements). One outdated testid (`element-container` vs. the current `stElementContainer`) was also silently causing a spacing fix to do nothing for several rounds — worth remembering that a CSS rule targeting a wrong testid fails silently, with no error, so "verify the testid name" should be an early suspect whenever a targeted override appears to have zero effect.

Also addressed directly: Streamlit's rerun-based navigation means every screen transition (including login → dashboard) is a genuine network round-trip with no way to make it truly instant while staying on Streamlit, which the user confirmed should remain the framework. Mitigated (not eliminated) with a fade-in transition and an explicit "Signing in…" spinner, so the wait reads as intentional rather than as unexplained lag.

---

## 20. Session Log: Incremental Demo-Data Flow, Persistent Notifications, Dashboard/Reconciliations Redesign (Aug 27-28, 2026)

### The problem this solves
Up to this point the dashboard's activity log lived only in `st.session_state` — it reset on every browser refresh and had no concept of "new data arriving over time." The user wanted a believable simulation of a live SaaS product: data arrives in waves, the app notices without polling, the user is told about it without having to go looking, and none of it breaks on a refresh, a server restart, or logging out and back in.

### The design: 3 deterministic batches, not a live feed
`gen_data.py`'s ~900-order dataset (itself already scaled up from an original ~260) was rescaled down to **exactly 180 orders, 60 per batch**, per explicit user direction — the original volume was "too much for a clean demo." Every order/settlement/ground-truth row carries a `batch_id` (1/2/3). Batch 1 is available the moment a merchant first logs in; batch 2 unlocks ~45 seconds after batch 1's reconciliation *completes*; batch 3 unlocks ~3 minutes after batch 2's completes. After batch 3, there is no batch 4 — ever.

Critically, **this is a demo stand-in for a future real webhook, not a fake permanent architecture.** The intended production shape (documented so a judge's "is this real?" question has an honest answer): a real Shopify/Razorpay webhook would push a "new data" event; the demo instead persists an availability timestamp and checks `now >= next_batch_available_at` on whatever rerun happens to occur next. **No `time.sleep()`, no background thread, no polling loop, no calling any API on a timer** — the UI is written so it doesn't actually care whether the "new data" event came from this demo mechanism or a real webhook later; that decision is fully isolated in `state_store.py`.

### Persistence: `state_store.py`
New per-merchant JSON file (`data/state/<merchant_id>.json`) holds: `current_batch`, `processed_record_ids` (every order/settlement ID ever reconciled, so a batch can never be double-processed even across a crash/restart), `reconciliation_runs` (most-recent-first, each a real saved result — see Section 21 for what got added to each run), `next_batch_available_at`, and three notification-lifecycle flags (`notification_created`, `notification_seen`, `notification_overlay_open` — see below). This is what makes "refresh the browser" and "log out, log back in" both fully safe: nothing that matters lives only in Streamlit's session state any more.

Login persistence (a related, previously-fragile piece) was hardened at the same time: `login.py` writes the authenticated merchant's email into `st.query_params` on success; `app_new.py` checks that query param on every fresh load and restores the session via a password-free `auth.get_merchant_by_email()` lookup — this is a *restore*, not a re-authentication, and can only ever resolve an identity that already passed a real password check once.

### Notification system: bell + automatic overlay, not "click the bell to find out"
An earlier iteration required the user to click the bell to discover new data. The user explicitly rejected this ("I DO NOT want that") and asked for an automatic, dismissible toast instead — matching how real SaaS products (and their own reference mockup) surface new data. Final design:
- The moment a scheduled batch's timer passes, a small floating card auto-appears near the top-right of whichever page is open, showing the *real* new-batch counts (Orders/Settlements/COD-Bank, read fresh from the same CSVs the real sync step reads — never hardcoded).
- **"Review & Reconcile →"** on the card: closes it, marks the notification read, navigates to the Reconciliations page — and explicitly does **not** start reconciliation on its own. The user must still click "Sync & Reconcile" there.
- **"Later" / "×"**: closes the card without marking it read and without touching the batch/timer state. The bell's red dot stays. Critically, the card does not pop back up automatically after this — it stays reachable via the bell only, and this had to be tracked as its own persisted flag (`notification_overlay_open`), separate from "has this batch's notification ever fired" (`notification_created`) and "has the user acted on it" (`notification_seen`) — collapsing these into one flag was tried first and produced either duplicate overlays after a refresh or an overlay that could never be dismissed for good.
- Each batch gets **exactly one** notification event, guaranteed by `notification_created` gating the auto-fire check — this was explicitly required ("no duplicate notifications," tested by fast-forwarding the timer and refreshing repeatedly).

### Dashboard vs. Reconciliations: a deliberate split, not duplication
The user, after seeing an early full-screen "syncing..." takeover page, asked for it gone and for a persistent, data-rich "Reconciliations" screen instead (explicitly referencing a real fintech-SaaS-style command-center mockup: KPI row, donut chart, amount-flow comparison, a "Risk Summary," a "Review Queue," and detailed recent-runs history). The resulting split:
- **Dashboard** — a lighter overview: 4 KPI cards (Total Reconciliations / Auto Matched / AI Resolved / Exceptions, all cumulative, all real), a simple Recent Reconciliations table, and a "+ New Reconciliation" button that **only navigates** to Reconciliations — it never starts a sync itself.
- **Reconciliations** — the actual operational surface. Before any reconciliation ever ran: a "ready state" card with real current-batch counts and a Sync & Reconcile button. Mid-sync: the same step-by-step progress list from the old full-screen page, but now rendered *inline*, sidebar and header still visible (no more separate route). After at least one run exists: a permanent results workspace — 8-card cumulative KPI row, a donut + `st.bar_chart` Amount Flow + a "Risk Summary" (Overpaid / At Risk / Unmatched, each clickable through to a filtered page) for the *most recent* run specifically, a Review Queue table of real flagged records, and a detailed Recent Reconciliations table. A slim, non-blocking banner (not a full card) surfaces a pending-but-unsynced batch here too — the primary channel for "new data exists" stays the bell + overlay, per the user's explicit instruction not to duplicate that signal as a permanent card on the results view.
- Sidebar now shows the company name as small static text under the Ledgr logo — explicitly **not** a dropdown, and explicitly removed from the main content header (which now only shows the current page's own title/subtitle).

### A real, quantified risk-safety derivation, not an invented category
The "Risk Summary" bucket (Overpaid / At Risk / Unmatched) was a genuine design question: the user explicitly forbade fabricating categories the data can't support. Resolved by deriving all three purely from fields `engine.py` already computes — `status`, `delta`, `matched_settlement`, `amount_at_risk` — with no new business logic: Overpaid = matched + settled for more than expected; At Risk = matched + settled for less, outside the fee band; Unmatched = exception with nothing matched at all. The three are mutually exclusive by construction, so they always sum cleanly and never double-count a record.

---

## 21. Session Log: Real AI Integration — Gemini, Not Claude (Aug 28, 2026)

### What changed from the plan in Section 15
Section 15 (and the Aug 26-27 session log) assumed the real AI Forensic Agent would call the **Claude API**. When the user actually had an API key ready, it turned out to be a **Google AI Studio (Gemini) key**, not an Anthropic one — and getting a fresh Anthropic key would have meant a new signup plus billing setup under real buildathon time pressure. The fix was a plain provider swap, not a re-scoping: `engine.py`'s AI seam (`ai_diagnose()` / `_llm_diagnose()`) was designed from the start to not care which vendor sits behind it, and that held — the only file that needed to change to switch providers was the new isolated `ai_client.py`. **Anywhere earlier sections of this file say "Claude API," read it as "whichever LLM `ai_client.py` currently wraps" — the commitment was to a real LLM call, not a specific vendor.**

### What actually got built
- **`ai_client.py`** (new) — isolated REST client (raw `requests`, no vendor SDK, matching `razorpay_client.py`'s established pattern) calling Gemini's Generative Language API with a forced JSON response schema: `{reason_code, confidence, explanation, evidence, recommendation}`. `reason_code` is constrained to the real `REASON_LEGEND` codes via the schema's own `enum`; anything else is treated as an invalid response.
- **`engine.py`** — `ai_diagnose()` now returns that same dict shape on both the offline and live paths (offline: `confidence`/`evidence`/`recommendation` are `None`/`[]`, since a hand-written if-else has no confidence to report). The original deterministic logic itself was untouched, just renamed to `_offline_diagnose()` and reused as `_llm_diagnose()`'s fallback whenever the real call fails for any reason. `emit()` gained three new optional fields purely to carry this data through to the results table — no tier, matching, or threshold logic changed.
- **`app_new.py`** — each saved reconciliation run now persists its individual flagged records (not just run-level totals), including the real `confidence`/`evidence`/`recommendation` when the live model produced them. The Review Queue / AI Review / Exceptions pages show a real percentage for AI-assisted records once available, "Pending" if AI was invoked but didn't return a score (offline stub or a failed live call), and "—" for records no AI ever touched.

### Non-negotiables that held under a real live test
- **The model never computes a number.** It receives facts `engine.py` already calculated (paise amounts, converted to `"Rs 1,234.56"` strings only for prompt readability, never touching the underlying arithmetic) and only ever returns a classification + explanation.
- **API failure never means guessing or crashing.** Verified with a *real* failure, not a mock: mid-testing, the Gemini free-tier quota was exhausted (a genuine `429`), and the fallback path worked exactly as designed — silently dropped to the same deterministic sentence used everywhere else, with a `[AI unavailable -- ...]` prefix, and `confidence`/`evidence`/`recommendation` correctly left empty rather than fabricated.
- **Live accuracy re-verified end to end**: full 180-record dataset, real calls, no mocking. Tier/disposition accuracy and clearing-decision precision/recall all stayed 100% (no money wrongly auto-cleared, no human bothered for nothing). Reason-code accuracy against the synthetic ground truth dropped very slightly, to 99.45% — one ambiguous overcharged-fee case got a different (still valid) classification than the ground truth assumed. This is the honest, expected cost of a real thinking model replacing a hand-coded heuristic, not a regression, and it's worth stating plainly rather than hiding if asked.

### Where AI coverage actually stops today (a real scope gap, not yet resolved)
`ai_diagnose()` is only ever called from one branch: "matched, but outside the known fee band" — reached by Tier 3 (has a gateway ref) and by Tier 4 (COD/bank, UTR-matched) when its shortfall is too large for a normal collection fee. **Tier 0 (COD timing) and Tier 5 (unmatched/ambiguous/orphan) get zero AI investigation today** — for the no-settlement-at-all and overdue-timer flavors of Tier 5 that's correct (no real judgement to make), but two Tier 5 sub-cases were already identified back in the Aug 26-27 "7-case taxonomy" session as genuine AI candidates that were never built: **ambiguous multi-candidate match** (case 3 — two settlements claim the same reference) and **orphan-settlement correlation** (case 2 — a credit with no order behind it, e.g. the shadow-duplicate scenario). The user was asked directly whether to extend AI to these next; **no decision had been made as of this writing** — check the latest conversation before assuming this is either in scope or out of scope.

**Superseded by Section 22 below:** the gap in the paragraph above was closed — `case_engine.py`'s `_AI_ELIGIBLE_TYPES` now covers `ambiguous_match` and `unmatched_settlement` (both cases 2 and 3), plus `unmatched_order`/`remittance_overdue`. Also, `engine.py` itself no longer calls any AI live at all — the entire real AI path moved to `case_engine.py`, called once per batch, after `reconcile()` finishes. Read this section (18-21) as historical record of how the AI integration *started*, not as the current architecture.

---

## 22. Session Log: Architecture Pivot to Batched AI + Persistent Case Store, and Full Ticket/Reconciliations UI Redesign (Aug 28-29, 2026)

### Why this pivot happened
Section 21 closed with real AI calls wired into `engine.py`'s Tier 3 branch, one call per flagged record. Under actual use (self-tests, a full-dataset regression run, a couple of UI-driven test batches, in fairly quick succession) this hit Gemini's **free-tier limits directly** — confirmed via the user's own Google AI Studio dashboard screenshot: 5 requests/minute, 20 requests/day, on the *unpaid* tier. The user explicitly declined to enable billing ("no i am not gonna do billing"). One call per flagged record was structurally incompatible with that ceiling at any real batch size, so this was a genuine architecture problem, not a bug to patch.

The user proposed the fix directly, in detail, before any code was written: keep the dataset/engine unchanged, do all deterministic work in Python, send only genuinely AI-eligible cases to Gemini, batch several cases per request, cache real results by an evidence fingerprint so unchanged cases never get re-sent, and when the quota is actually exhausted, mark the case honestly "AI hasn't looked yet" rather than fabricating a result or crashing.

### The dataset shrank again, this time for a documented reason
`gen_data.py` was resized a second time: from 180 orders / 3 batches (Section 20) down to **exactly 100 orders across 2 batches of 50** — the user's own reasoning: the buildathon only requires demonstrating 50+ records through the agent, so a third batch added demo complexity without adding required coverage. Confirmed on disk: `data/orders.csv` has 104 data rows (52/batch — 50 from the shuffled scenario `PLAN` plus a couple of hand-built special cases per batch: bulk-COD orders, orphan-credit settlements, one shadow-duplicate settlement), `data/settlements.csv` has 95. Re-validated after the resize: 100% tier/disposition accuracy, 100% clearing-decision precision/recall against `ground_truth.csv`.

### The new AI architecture (`case_engine.py`, new — this is now the ONLY place a live Gemini call happens)
`engine.py` was simplified back to **100% network-free** — `ai_diagnose()` always returns the offline deterministic heuristic now (renamed `_offline_diagnose()`, logic itself untouched). All real AI investigation moved to a new module, `case_engine.py`, which runs once per batch, strictly after `reconcile()` finishes:

1. **Only genuinely AI-eligible case types get sent at all** (`_AI_ELIGIBLE_TYPES`): `partial_payment`, `overpayment`, `ambiguous_match`, `unmatched_settlement`, `unmatched_order`, `remittance_overdue`. Explicitly excluded: `pending_settlement` (still inside its normal COD window — not broken, nothing to investigate) and any cleanly auto-matched record (never becomes a "case" at all).
2. **Batching** — `ai_client.investigate_batch()` sends up to `DEFAULT_BATCH_SIZE = 5` cases in a single Gemini request (structured JSON output, one response item per case, keyed back to `case_id`), instead of one call per case. This is the direct fix for the RPM/RPD ceiling — it caps request *count*, not case count.
3. **Evidence-hash caching** — `_evidence_hash()` fingerprints the facts that actually matter to a case (type, expected/received/delta, candidate IDs, reason) via SHA256. If a case's hash is unchanged from its last real investigation, the stored result is reused — zero new API cost. If the hash changes (new candidate appeared, amounts shifted), it's queued for a fresh call. Verified correct with a deliberately isolated, zero-API-cost test: a fabricated valid cached entry got reused; a manually changed hash correctly triggered re-investigation.
4. **`ai_pending` — a fourth, honest case-lifecycle state**, distinct from `manual_review`. `manual_review` means AI genuinely investigated and is recommending a human decide. `ai_pending` means AI hasn't had a chance to look yet (usually a 429). This distinction was tested against **real, repeated rate-limit hits** during development, not simulated — confirmed it never crashes, never fabricates a result, and stays visually distinct in the UI (shown as its own slice in the Reconciliation Resolution Funnel, not folded into Manual Review).
5. **`AUTO_RESOLVE_CONFIDENCE_FLOOR = 85`** — even when Gemini recommends `resolve`, a confidence below 85 is downgraded to `manual_review` in code, regardless of what the model said. Mirrors this project's standing "never auto-clear without justification" rule structurally, not just as a prompt instruction.
6. **The one controlled agentic step**: `investigate_case_followup()` — when Gemini names specific `missing_evidence`, a user-triggered "Investigate Further" button fetches what's realistically fetchable (currently: a customer's other order history — the only evidence source this system actually has beyond the CSVs) and makes exactly one more Gemini call for a final verdict. Never automatic, never looped further. This is the one piece of "agentic AI" in the project, and it was a deliberate, explicit compromise the user proposed themselves after discussing RAG/LangChain/MCP and agreeing those were the wrong scope for this timeline.
7. **Direct-answer-first Ask AI** — `try_direct_answer()` answers common questions (case ID lookup, "which orders are still pending", "how much is outstanding", "which cases are AI-pending") straight from the persisted case store via pandas, with zero API cost, and only falls through to a real Gemini call (`ai_client.ask()`) for genuinely novel questions. Verified live: pattern-matched questions return instantly with no API call; a vague question ("ok") correctly falls through to a real call.

### The persistent case model (`state_store.py`'s `cases` dict)
Every non-clean record becomes a **case** — a persistent dict surviving Streamlit reruns, browser refresh, and logout/login (same JSON-per-merchant mechanism as the rest of `state_store.py`). Key fields: `case_status` (lifecycle: `pending_settlement` / `needs_ai` / `ai_pending` / `ai_recommendation` / `manual_review` / `exception` / `resolved`), `case_type` (what kind of discrepancy), `ai` (the full investigation result or `None`), `candidates`, `resolution` (who resolved it, how, and now also the justifying **comment** — see below), `bookmarked`, `comment`, and a full `history` timeline. `escalate` (an AI action, when there's genuinely nothing to weigh — no candidates, no evidence) now maps to its own `exception` status, distinct from `manual_review` (which means AI found real evidence but couldn't resolve unambiguously) — this distinction was confirmed against the user's own reference mockup showing a 4-way split (AI Resolved / AI Recommendation / Manual Review / Exception).

Delayed settlements are handled without duplicating cases: `state_store.pending_settlement_order_ids()` re-includes still-open orders from earlier batches in the next batch's input, and `upsert_case()` preserves `created_at`/`history`/human `resolution` across re-evaluation, so a late-arriving settlement updates the *same* case_id instead of creating a new one. A real bug was found and fixed here during testing: an order with a known `bank_utr` but a settlement deliberately delayed to a later batch landed as a hard `unmatched_order` exception in the interim batch instead of the expected soft `pending_settlement` wait state, because `engine.py`'s Tier-0 pre-check only triggers when `bank_utr` is empty. Fixed by broadening which case types get re-evaluated across batches, not by changing `engine.py`.

### The Reconciliations page rebuild
Rebuilt to match a detailed reference mockup the user provided, through several iterative rounds of screenshot feedback: 4 KPI cards (dropped a planned "vs last month" trend line — the user explicitly rejected fabricating a comparison the data doesn't support), a **Reconciliation Resolution Funnel** (replacing the earlier CSS donut chart — stacked bars: Total Records → Deterministically Matched → AI Investigated → AI Resolved → Manual Review → Exceptions, plus a conditional "AI Pending" row shown only when nonzero), an **Awaiting Settlement** widget (pending-settlement cases pulled *out* of the Review Queue — the user's own insight: "they are not there for getting reviewed" — into their own list), and a **Review Queue** with 5 live filter pills (real counts, not decorative), sorted by AI confidence descending, with a small inline confidence mini-bar per row.

### The AI Investigation Ticket page — redesigned twice, based on direct feedback that the first pass was too dense
The first rebuild (matching an initial mockup) packed 8 separate cards, tabs, and two callout boxes onto one page. The user called this out directly ("doesn't this screen look too congested?") and shared a leaner reference mockup. Final design, confirmed piece-by-piece with the user before being built:
- **Three flat columns**, not eight cards: **Case Summary** (money + order/settlement metadata together), **AI Analysis** (Finding → Evidence → Recommendation as one narrative), **Supporting Documents** (compact popover chips — Order Details, Settlement Details, Fee Structure/MDR, Candidate Matches, Activity Log — each shown *only* when that case actually has the underlying data; a case with no order side genuinely shows no Order Details chip, never an empty one).
- **Fee Structure (MDR) chip is real, not decorative** — it computes the actual tolerance band from `config.py`'s own `fee_band()` function, the same constants `engine.py` uses for Tier 2, shown for reference against this specific case's real shortfall.
- **Bookmark** replaces a planned "Actions ▾" dropdown entirely, per the user's explicit preference — a single persistent per-case toggle (`state_store.toggle_bookmark()`), survives reruns/refresh.
- **Comments, with a real, deliberately asymmetric rule**: accepting AI's recommendation auto-fills the comment from AI's own `next_step` text (editable, never silently hidden); keeping a case for manual review is **blocked** until a comment is typed — verified live via `AppTest`, including confirming the block correctly refuses to resolve and shows an inline warning, and that a typed comment persists into `resolution.comment` on success. The comment box itself is a collapsed `st.expander` by default (the user's own instruction: "make the comments box collapsed/less prominent initially... it only needs to become important when manually resolving") and auto-opens exactly when that block fires.
- **Investigate Further shows real, granular progress** — 4 steps (Identifying missing evidence → Retrieving data → Analyzing with AI → Updating result), each tied to an actual function call completing (`case_engine.fetch_missing_evidence()`, `case_engine.build_case_context()`, `ai_client.investigate_followup()`, `case_engine.apply_ai_result()` — the last two promoted from private to public specifically so the ticket page could call them individually instead of through one opaque wrapper). Not a cosmetic animation. Verified end-to-end with the real Gemini call mocked (to avoid spending quota on a test) — confirmed the confidence delta (e.g. 40% → 90%, shown as a "▲50%" badge next to the header's confidence pill) is captured and displayed correctly.
- **A real bug found and fixed after building this**: disabled buttons (e.g. "Accept & Reconcile" when AI recommended `escalate`, not `resolve`) were still rendered with their full-color, fully-clickable-looking CSS, because the `!important` color overrides didn't account for Streamlit's native `:disabled` state. The user caught this from a live screenshot ("accept & reconcile button is not clickable why"). Fixed by adding explicit `:disabled` style overrides (muted background, dimmed text, `not-allowed` cursor) — the underlying enable/disable *logic* was already correct; only the visual signal was misleading.
- Button hierarchy, per explicit final feedback: **Accept & Reconcile** (renamed from "Accept Recommendation" specifically because "it actually changes the reconciliation state" — the user's own reasoning, for a beginner-friendly label) is primary/leftmost; **Investigate Further** stays secondary/purple-outline, middle; **Keep for Manual Review** stays neutral, rightmost.

### What's verified working, with real evidence (not just "should work")
- Batching + evidence-hash caching: confirmed a cached result is reused when evidence is unchanged, and correctly invalidated when it changes.
- `ai_pending` under genuine repeated 429s across multiple real test rounds: never crashed, never fabricated a confidence score or reasoning.
- Cross-batch delayed settlement: a single case_id (`CASE-ORD-00024` in one test run) tracked cleanly from `unmatched_order → manual_review` in batch 1 to `settlement_matched → resolved` in batch 2, with a continuous history timeline — no duplicate case created.
- The mandatory-comment / auto-fill-on-accept / disabled-button logic: all verified via `AppTest`, including negative cases (blocked resolution, correctly-disabled buttons for an `escalate` recommendation).
- The Supporting Documents chips correctly gate on real data: an orphan-settlement case with no order side shows only Settlement Details, Candidate Matches, and Activity Log — no empty Order Details or Fee Structure chip.

### What's NOT done — honest, current list of gaps
1. **COD bulk remittance (one settlement UTR covering many orders) is still not modeled.** `engine.py`'s `by_utr` matching remains strictly 1-to-1. This was flagged as a genuine architectural gap back in Section 18 ("Case 5" of the original 7-case taxonomy) and has never been built — it's a real subset-sum/partition problem with structural ambiguity, not a quick addition, and would need explicit design discussion before touching per this project's own rules.
2. **The Risk Summary widget on the Reconciliations page still reads from the old per-run `flagged_records` snapshot**, not the new persistent case store the rest of the page now uses. Not incorrect, just a real, un-migrated inconsistency — a candidate for a follow-up pass.
3. **The "Investigate Further" real Gemini call has never been observed succeeding end-to-end against the live API** — every live attempt during development hit the rate limit before completing the second call. The orchestration itself was verified correct with the Gemini call mocked, but the actual live path remains genuinely untested by direct observation.
4. **A dead `RECONAI_LLM=1` line remains in `.env` and `.env.example`**, left over from before `engine.py` stopped reading any environment toggle for AI. Harmless (nothing reads it any more) but should be deleted as basic hygiene.
5. **Sidebar stub pages** (Transactions, Reports, Data Sources, Settings) remain "coming soon" placeholders — never scoped as buildathon deliverables, so not a regression, just unfinished surface area if a judge clicks around.
6. This file's own Sections 15 and 18-21 describe the **Claude API** as the intended provider and a **3-batch/180-record** dataset — both superseded (see the note appended to the end of Section 21, and this section). Read historical sections for how decisions evolved, not as the current state.

### What worked well, worth remembering as a pattern
- Proposing the batching/caching architecture in plain language *before* any code was written (the user's own explicit "discuss first, don't build yet" instruction) avoided building the wrong thing under real quota pressure — the eventual implementation matched the discussed plan almost exactly.
- Every UI redesign in this phase was driven by the user's own screenshots and mockups, confirmed piece-by-piece, rather than unilateral design choices — this kept iteration cost low (no large rebuilds from a wrong guess) and caught real usability problems (the first ticket redesign being "too congested") early via direct feedback rather than after the fact.
- Treating a real rate-limit hit as a feature to verify, not just an error to suppress, produced actual confidence that the honest-degradation path works — this is a stronger demo claim ("we tested this failing for real and it never lied") than "we handle errors gracefully" asserted without evidence.
---

## 23. Session Log: Streamlit Retired, React + FastAPI, Multi-Provider AI (Aug 29-30, 2026)

### The architecture changed shape

The Streamlit UI is gone. `app.py` (1848 lines) and `app_new.py` (2504 lines) were deleted in commit `e587a0b` and replaced by a React 19 + TypeScript + Vite SPA in `frontend/`, backed by a new FastAPI layer, `api.py`.

**Nothing was lost from the Python core.** `engine.py`, `case_engine.py`, `state_store.py`, `razorpay_client.py`, `shopify_client.py`, `gen_data.py` and `config.py` are untouched and still own every decision. Sections 1-22 above remain accurate about the reconciliation engine, the AI case layer and the data model — treat only their UI descriptions as historical.

The rewrite was the user's call, made with a clear-eyed view of the tradeoff: Streamlit had repeatedly fought us on layout, modals, disabled-button styling and full-page reruns, and ~6 days remained. The Python core surviving intact is what made it affordable.

### `api.py` — 22 endpoints, and a deliberate boundary

The API orchestrates and serialises; it never decides. No matching rules, no confidence scoring, no financial arithmetic live in it. Money crosses as integer paise exactly as the engine produced it, because formatting in two places is how a reconciliation tool quietly loses money.

Auth is an in-memory bearer-token map — an honest match for `auth.py`'s hardcoded demo accounts. Every API restart logs everyone out; that is expected, not a bug.

Three endpoints worth knowing about:

- `GET /api/transactions` returns EVERY record including clean auto-matches, by re-running the engine over already-processed batches rather than keeping a second stored copy that could drift from what the engine actually decided.
- `GET /api/cases/{id}/evidence` returns the real order, settlement and fee-tolerance records behind a case, each `null` when no such record genuinely exists (an orphan settlement has no order; an unmatched order has no settlement).
- `POST /api/cases/{id}/draft-message` writes an outbound message. There is deliberately **no send endpoint**.

### Multi-provider AI, and why it is not quota farming

The user raised collecting several API keys to escape Gemini's 20/day free tier. The first answer was a caution: rotating keys from accounts created to dodge a per-account limit is quota circumvention. That objection was withdrawn once it emerged the keys were for **different providers** — OpenRouter, Groq — each a separate account with its own independent limits. Failing over between distinct vendors is ordinary production resilience, and it is a genuinely stronger answer for a judge than "we rotate free keys".

Chain: **Gemini → OpenRouter → Groq**, configured in `PROVIDER_ORDER`. Missing keys are skipped silently. Crucially, **if every provider fails the case still lands on `ai_pending`** — failover adds capacity, it never removes the honesty path that says "AI genuinely could not look at this".

Each verdict records which `provider` produced it, because different models calibrate confidence differently and an unattributed 80% is not auditable.

Three real integration lessons, none of which were guessable:

- **OpenRouter reserves your full `max_tokens` against your credit balance before running anything.** Unset, it reserves the model maximum (65k+) and a free account is refused with a 402 having spent nothing.
- **Groq's free tier limits tokens-per-minute (8000), not requests**, counting prompt + `max_tokens` together, and reports the breach as a 413.
- **Model availability must be queried, not assumed.** The first Groq model chosen did not exist on the account.

### Ask AI: the direct-answer path was removed from the primary route

Ask AI previously tried a Python keyword matcher first and only called a model when that returned nothing. A screenshot from the user showed why that was wrong: asked *"how much manual work did we eliminate in this session"*, the matcher recognised a keyword and confidently returned the **outstanding total** — a fluent, wrong answer. With three providers there is capacity to route everything to a model, so the order was reversed. `try_direct_answer()` survives only as a last-resort fallback when every provider is exhausted, where a correct partial answer still beats an error.

Two further fixes came from the user's own domain knowledge:

- Asked which case to prioritise, the model picked a **Rs 999 overpayment** over a **Rs 9,999 unrecovered order**. It was reasoning correctly over the wrong field: the context passed `delta`, and an order that never settled has a delta of zero because nothing arrived to compare against. The context now carries `amount_at_risk`, and the prompt states the economics — money not received outranks money over-received, because an overpayment is already in the account while unrecovered money can become permanently unrecoverable.
- Asked a customer's name, the model said the data contained no personal information. It was being honest: `build_ask_context` never sent `customer_name`. Contact details for open cases are now included, and `ask()` takes the last six conversation turns so follow-ups ("his name?") have an antecedent — explicitly labelled in the prompt as reference-resolution only, never a source of facts.

### Draft a message — Case 7, finally built

The 7-case taxonomy from Section 18 listed "human-facing text generation" as the one AI task with zero financial-decision risk. It now exists: AI drafts a message about a case, the user edits it, and their own mail client sends it.

Recipients are derived from the case's real facts — a COD case offers the courier, an online payment offers the gateway, an orphan settlement with no customer offers nothing and the panel hides itself. Where no address is held (courier and gateway support addresses are not in this dataset) it says so rather than inventing one. The prompt forbids promising refunds, accepting fault, or setting deadlines, and the draft lists the exact case facts it cited so a human can audit it in seconds.

### Current status — roughly 70% complete (Aug 30)

**Done:** the deterministic engine (100% validated), the case layer, batched AI with evidence-hash caching, three-provider failover, 22 API endpoints, and all seven React screens — login, dashboard, reconciliations, cases, case detail, transactions, settings — plus Ask AI, message drafting, supporting documents, and resolve / reopen / bookmark.

**Left, in rough priority:**

1. Four API methods have no UI calling them: `investigateFurther` (the controlled agentic step — arguably the most impressive AI feature in the project and currently unreachable from the interface), `retryAi`, `setComment`, `getSettings`. Roughly 2-3 hours.
2. `run_date` is hardcoded in `caseUtils.ts` rather than read from `/api/state`. It matches today, so nothing is visibly wrong, but aging would silently diverge from the engine if the backend date ever changed.
3. Page `<title>` never updates per route; bell dismissal is local-only and returns on refresh.
4. **No clean end-to-end rehearsal has ever been performed.** Every verification so far has been piecemeal, frequently while a provider was rate-limited or — twice on Aug 30 — while an orphaned server process was serving stale code. That pattern hid three real bugs. Assume the first uninterrupted run finds more.
5. Visual QA across dark mode, responsive layouts and empty states. Not verifiable from a terminal; the user has caught several visual bugs by screenshot that automated checks could not.
6. Documentation drift — this file, `CLAUDE.md` and `frontend.md` all need re-reading before the deadline.
7. The five-minute demo video, which is a required deliverable and not started.

The honest read: the remaining engineering is small (~5 hours). The remaining *risk* is that nobody has yet watched this system work start to finish in one sitting.

---

## 24. Session Log: COD Remittance Detail + Number-Consistency Audit (Aug 31 - Sep 1, 2026)

### 24.1 What shipped

**Courier COD remittance detail** -- the last unbuilt item from the 7-case
taxonomy (Section 15, case 5). A bulk COD payout arrives as one bank credit;
`engine.py`'s `by_utr` matching is 1:1, so it booked the orders as unpaid AND
the credit as unexplained. The same money was counted twice, and the two halves
gave contradictory instructions: "chase the courier for the overdue
remittance" on the orders, "determine if it should be refunded" on the credit.
Delhivery had already paid.

Now modelled the way it works in reality: the courier publishes a remittance
file alongside the payment, one row per delivered order carrying the order id.
Matching is a **join, not a search**.

### 24.2 New files

| File | Purpose |
|---|---|
| `remittance.py` | Deterministic join + checksum + 7 discrepancy detectors. Zero AI. |
| `test_remittance.py` | 14 checks: every discrepancy kind, plus the guards |
| `data/remittances.csv` | Synthetic courier remittance detail (generated) |
| `frontend/src/components/cases/CaseRemittancePanel.tsx` | Shows the per-order breakdown on a case |

### 24.3 The data model (unchanged count: still THREE sources)

Remittance detail belongs to the **existing Bank / COD source**. It is the
per-order breakdown behind a bank credit, not a separate integration:

```
1. Shopify        -> orders
2. Razorpay       -> gateway settlement feed
3. Bank / COD     -> bank credits  +  courier remittance detail   <- extended
```

Reported under `bank` in `/api/sources` with a `remittance_rows` count. No new
sidebar entry, no fourth source.

`data/remittances.csv` columns:
`settlement_utr, order_id, awb, cod_collected, cod_fee, freight_fee,
net_payout, remitted_on, courier, batch_id`

`batch_id` matters: remittance rows are revealed with their own batch, exactly
like orders and settlements. Without it a later batch's rows are visible while
its bank credit is not, and the checksum reports a missing credit for money
that simply has not arrived yet.

### 24.4 The rule that makes it safe

**A batch links NOTHING unless its rows sum exactly to the bank credit.**
Unproven paperwork must never clear money. When the checksum fails, the batch
becomes an exception and the orders stay open.

Seven detectors, each provable from the join rather than inferred:
`order_missing_from_remittance`, `remittance_order_unknown`,
`order_in_multiple_batches`, `batch_checksum_mismatch`,
`cod_collected_mismatch`, `cod_fee_over_band`, `remittance_batch_without_credit`.

`cod_fee_over_band` reuses `config.fee_band(...)` -- the same contracted band
`engine.py` enforces at Tier 2/4. Fee policy stays defined in ONE place.

### 24.5 A rejected design worth recording

The first proposal was **subset-sum**: group unmatched COD orders by courier
and date window, find the subset whose total minus the COD fee equals the
credit. It was prototyped against the real dataset before any project code was
written, and it failed: with a `fee <= 2.5%` inequality it returned **12
candidate subsets** for one credit, and confidently mis-matched an orphan
credit that has no orders behind it at all.

Tightening the fee band and requiring a courier name in the narration got it to
a unique correct answer -- but it was still producing a *probable* answer where
a certain one exists. The remittance file makes the question a lookup.

**The principle:** AI (or heuristics) earn their place only where a
deterministic answer is structurally unavailable. Here it was available; we
were just not reading the right file.

### 24.6 The number-consistency audit

Six real bugs where different screens computed the same figure differently:

| Bug | Was | Now |
|---|---|---|
| Expected money | Reconciliations Rs 3,65,137.16 vs Reports Rs 3,28,142.70 | one de-duplicated source |
| Record total | Dashboard 123 / Recon 112 / Reports 112 | `totalReconciledRecords()`, 112 everywhere |
| "178 settlements" | counted any record with money received | counts by `record_kind` -> 87 |
| "Auto matched" | included COD still inside its window | own `awaiting_settlement` bucket |
| Reports "Settled by rules 102" | counted unmatched exceptions as settled | shared `work_split` -> 79 |
| Donut partition | right only by coincidence of this dataset | explicit order-side subtraction |

**Root cause in every case:** two places deriving one number from different
sources. **The standing rule now:** any figure shown in two places must have
ONE definition in code.

### 24.7 Vocabulary (use these consistently)

| Bucket | Meaning |
|---|---|
| **Auto matched** | rules settled it, no human needed (includes remittance-resolved) |
| **Awaiting settlement** | COD inside its window -- not a failure, a clock |
| **AI recommendation** | AI found a lead a human can accept or reject |
| **Needs investigation** | AI checked and found no conclusive path |
| **Being investigated** | transient; only while a batch is still running |

These sum to total records by construction. "AI Resolved" was removed as a
label -- those records are exactly the ones that become open cases.

**Manual work eliminated** =
`(auto matched + AI handled) / (total records - awaiting settlement)`.
AI-handled counts as eliminated because the investigation was done for the
human even though the decision is not. COD inside its window is excluded from
the denominator: there is no work to eliminate on money that has not arrived.

### 24.8 AI review latency

Verdicts now persist **per chunk**, not per batch
(`investigate_new_cases_batched(..., on_chunk_done=...)`). The review queue
used to sit at 0 for ~2 minutes then fill all at once; it now shows 5 cases at
7s, 10 at 31s, 15 at 97s. Remaining gaps are Groq's tokens-per-minute ceiling.

A header refresh button (with a live count of cases still being investigated)
and a "figures are provisional until this clears" banner on Reconciliations
make the in-progress state legible.

### 24.9 Verified state

```
test_remittance.py            14/14
engine.py vs ground_truth     106 scored, tier/disposition/reason 100%
                              precision 100% (0 false clears), recall 100%
bulk records                  6/6 resolved, amount_at_risk 0
at risk                       Rs 81,481.80 -> Rs 74,717.68
frontend                      tsc clean, production build clean
```

### 24.10 Known limitations (state these plainly)

- **Split payout** -- one order paid across two settlements. The inverse of
  bulk remittance; not modelled.
- **Late chargeback** reversing an already-cleared record.
- **Narration parsing** -- formats differ per courier per bank; narrations are
  carried and displayed, never parsed.
- **Stage 2 remittance work** (discrepancy-audit reporting, dispute-deadline
  tracking) deliberately not built.
- Demo remittance data is deliberately CLEAN so the happy path is what shows;
  every failure mode is proven by `test_remittance.py` fixtures instead.

### 24.11 Process note

A `git restore` mid-session discarded every uncommitted change to tracked
files (no stash, nothing recoverable). Only untracked new files survived.
**Commit after each working increment.**

## 25. Session Log: Working Notes, and a Transactions/Cases Consistency Pass (Sep 1-3, 2026)

Pre-demo hardening. One new feature (working notes), and a set of real
consistency bugs between the Transactions and Cases screens found by the user
directly clicking through the app -- the same "one definition per number"
failure class as Section 24.6, this time in status labels and case linkage
rather than money totals.

### 25.1 Working notes -- a partial finding that doesn't resolve the case

`state_store.set_comment()` and `POST /api/cases/{id}/comment` already
existed and worked; they were simply never wired to any UI. Built:

- **`CaseNotesPanel.tsx`** (new) on the case detail page -- a textarea + "Save
  note" that calls the existing endpoint. Explicitly does **not** touch
  `case_status` or `resolution` -- the case stays in the open queue. Re-seeds
  on `case_id` change so navigating between cases can't save a note onto the
  wrong one.
- **`hasWorkingNote()`** in `caseUtils.ts` -- the one definition: open for
  review AND a non-empty comment. A resolution comment does not count; that
  case is closed.
- **"My notes" filter pill** on Cases, plus an amber `NOTE` badge in
  `CasesTable.tsx` (hover shows the note text).

Verified live: saving a note on an `ai_pending` case left it `ai_pending`,
`resolved: false`, with a `comment saved` history entry -- confirmed via a
direct API call, not just the UI.

### 25.2 Transactions was contradicting Cases -- three real bugs

`GET /api/transactions` re-runs `engine.py`'s stateless, per-run tier output
every time (see Section 23's note on that endpoint). It had no way to know a
case built on top of a record had since been resolved by a human, or by the
remittance join proving a bulk-COD credit already arrived. Caught directly by
the user clicking a bulk-COD order on Transactions and finding it still said
`EXCEPTION -- Matched settlement: Not linked` while its own case page said
`Resolved automatically`.

**Fix: `transactionUiStatus()` now checks the linked case first.** If the
case is resolved, that overlays whatever the engine's frozen tier read says.
Threaded through `transactionDisplayFields()` too -- `matched_settlement`,
`reason_label`, `explanation`, and `amount_at_risk` in the detail drawer all
now prefer the case's current values over the record's frozen ones once
resolved, so the drawer stops saying "resolved" and "Rs 999 at risk" in the
same panel.

**Bug 2: "View case" was hidden for exactly the cases worth viewing.**
`canViewCaseForTransaction` excluded anything already resolved
(`isOpenForReview` is false once resolved), so the richest part of the demo
-- the remittance breakdown behind a bulk-COD order -- was one click short of
reachable from Transactions. Now: `isOpenForReview(case) ||
case.resolution.resolved`.

**Bug 3: a candidate settlement in an ambiguous-match case had no case link
at all.** `ORD-00014` has two settlements (`STL-00014`, `STL-00014-D`)
competing for the same amount -- real evidence AI already weighed inside
`CASE-ORD-00014`. But a case is filed under one `record_id`, and for an
ambiguous match that's the ORDER's id -- the competing settlements exist only
inside the case's `candidates` list, never as their own tracked record. So
`api.py`'s `cases_by_record` lookup found nothing for either settlement, and
they showed as raw, unlinked `EXCEPTION` rows -- looking uninvestigated when
they were the central evidence of an already-worked case.

Fixed in `api.py`: every case's `candidates` list is walked and each
`settlement_id` found there is added to `cases_by_record` via `setdefault` --
so a settlement that genuinely owns its own case (a true orphan,
`unmatched_settlement`) is never overridden by merely being named as someone
else's candidate. **Confirmed via direct API test:** a genuine orphan
settlement (no order in any batch, ever) was already correctly handled before
this session -- `engine.py` emits it self-referentially so its case is filed
under its own id. The gap was narrower: only a settlement referenced as a
*candidate* inside a different case's evidence.

### 25.3 Vocabulary cleanup on Transactions (extends Section 24.7)

The `'ai_review'` bucket predated Section 24.7's AI recommendation / needs
investigation split and was never updated -- it derived from `engine.py`'s
structural `ai_assisted` tier flag, not the case's actual AI verdict, so
"needs investigation" cases and "AI recommendation" cases were shown under
one undifferentiated "AI review" label. Split to match the same
`aiReachedVerdict` / `needsInvestigation` distinction used everywhere else,
with the same fallback-to-engine-flag only for the rare record with no case
object loaded yet.

Added a **Resolved** status (teal badge, distinct from `matched`'s emerald --
"cleared on the first pass" and "was flagged, then resolved" are different
facts worth telling apart at a glance).

**Removed the `Exception` filter option entirely** (user's explicit call,
after 25.2's fix): every genuinely exceptional record now becomes a case and
is classified by that case's real AI verdict, so the raw `'exception'` bucket
should be empty in practice. It survives internally only as a defensive
fallback for a record with no case object at all -- not worth exposing as
something to filter for.

### 25.4 Process note: two backends were running on two different ports

During this session's verification, a backend was started on port 8000 to
test the `api.py` fix -- but the frontend's `vite.config.ts` proxies `/api`
to **port 8001**, an older process left running from earlier in the project
that was never touched by the fix. Every "it's not working" observation
traced back to testing against the wrong port's stale code, not a bug in the
fix itself. **Before restarting the backend, check `vite.config.ts`'s proxy
target, not just what "the backend" conventionally means** -- and remember
every restart clears the in-memory token map, so the browser session needs a
fresh login afterward, not just a page refresh.

### 25.5 Verified state

```
frontend                      tsc clean, production build clean (409 KB)
working notes                 saved via direct API call: case_status
                               unchanged (ai_pending), resolved: false
candidate settlement linkage  STL-00014 / STL-00014-D -> CASE-ORD-00014,
                               confirmed via curl against the live API
transaction status overlay    bulk-COD order: EXCEPTION -> RESOLVED (teal),
                               "Matched settlement" STL-BULK01 (was "Not linked"),
                               "At risk" row correctly hidden (was Rs 999)
```
