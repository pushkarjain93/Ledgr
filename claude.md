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