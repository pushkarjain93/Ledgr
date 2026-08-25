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

Current important files include:

- `app.py` — application/UI layer
- `engine.py` — core reconciliation engine and matching logic
- `config.py` — configuration and thresholds
- `gen_data.py` — demo/test data generation
- `validate_data.py` — data validation
- `schema_map.py` — schema/field mapping
- `customers.csv` — customer/order-related data
- `review_log.csv` — review/audit information
- `data/` — project data
- `.streamlit/` — Streamlit configuration

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