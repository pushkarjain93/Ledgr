# Ledgr

**AI-assisted payment reconciliation for e-commerce merchants.**
Built for the Razorpay Buildathon — Track 04, "AI Finance Controller."

Ledgr reconciles orders, gateway settlements, and courier/bank COD credits
automatically, uses AI only where a deterministic rule genuinely cannot answer,
and never lets AI move money on its own.

---

## The problem

A merchant's money shows up in three disconnected places:

1. **Orders** — the store (Shopify).
2. **Online settlements** — Razorpay.
3. **COD cash** — remitted by the courier straight to the merchant's bank.
   Razorpay has zero visibility into this money.

Someone on the finance team manually cross-checks all three every week. Most
of it is boring and mechanical (does the amount match?); a small slice is
genuinely ambiguous and needs judgment (why is this ₹40 short?). Ledgr
automates the boring 85–90%, uses AI for the genuinely ambiguous slice, and
routes anything still uncertain to a human — with the evidence already
gathered.

---

## What it actually does

- **Deterministic 5-tier matching engine** (`engine.py`) — exact reference
  match, known fee-band match, COD UTR match, then escalation tiers for
  ambiguous/unmatched records. Network-free, stateless, and validated against
  a hand-built ground truth file: **100% tier / disposition / reason-code
  accuracy, 0 false clears, 0 missed clears** on the demo dataset.
- **Bulk COD remittance matching** (`remittance.py`) — a courier pays out
  *once* for many delivered orders. Ledgr joins the courier's own per-order
  remittance file against that bank credit and only links the money if the
  rows sum to the credit **exactly, to the paisa**. If they don't, it's
  surfaced as a discrepancy — never silently cleared. No AI involved by
  design; when structured data can answer the question, a lookup is used
  instead of a guess.
- **AI case investigation** (`case_engine.py`, `ai_client.py`) — every record
  the engine can't cleanly resolve becomes a case. AI reads the evidence,
  explains the likely reason, and returns a confidence score. A result below
  a hard confidence floor is downgraded to manual review **in code**, not
  just by prompt instruction. AI never auto-clears a high-risk case and never
  drafts anything more than a message a human still has to send.
- **Multi-provider AI failover** — Groq → OpenRouter → Gemini, each an
  independent account/limit. If every provider is unavailable, a case is
  marked `ai_pending` — an honest "no one has looked at this yet" state,
  never an invented verdict.
- **Working notes** — a reviewer can leave a partial finding on a case
  ("courier confirmed pickup, awaiting POD scan") without resolving it. The
  case stays in the queue, filterable later, so investigation context isn't
  lost.
- **Draft outbound messages** — AI drafts an email to the courier, gateway,
  or customer about a case. Ledgr never sends anything itself.
- **One definition per number** — every figure shown on more than one screen
  (Dashboard, Reconciliations, Reports) is computed once, on the backend, and
  passed through unchanged. No two screens can silently disagree. The same
  rule applies to case linkage: the Transactions view overlays a case's real,
  current status (including remittance auto-resolution) instead of repeating
  the reconciliation engine's frozen first-pass read.

---

## Architecture

```
┌─────────────────┐        HTTP / JSON         ┌──────────────────────┐
│  React + Vite    │  ───────────────────────▶  │  FastAPI (api.py)    │
│  frontend/        │  ◀───────────────────────  │  transport layer only│
└─────────────────┘                              └──────────┬────────────┘
                                                             │
                                   ┌─────────────────────────┼─────────────────────────┐
                                   ▼                         ▼                         ▼
                         engine.py (rules)          case_engine.py             state_store.py
                         5-tier deterministic        AI investigation,         per-merchant JSON,
                         matching, network-free       batching, caching         case lifecycle,
                         remittance.py                                          survives restarts
                         bulk COD join + checksum
                                   │
                                   ▼
                          ai_client.py — Groq / OpenRouter / Gemini failover
```

`api.py` is deliberately a thin transport layer: it orchestrates and
serializes, it never computes a financial number or a matching decision
itself. Money crosses the wire as **integer paise** end to end; formatting to
₹ happens only at render time in the frontend.

---

## Tech stack

| Layer | Choice |
|---|---|
| Reconciliation engine | Python, pandas |
| API | FastAPI + Uvicorn |
| AI providers | Groq, OpenRouter, Gemini (structured JSON output, tried in order) |
| Persistence | Per-merchant JSON on disk (`data/state/`) |
| Frontend | React 19, TypeScript, Vite, React Router, Tailwind CSS |
| Auth | In-memory bearer tokens over hardcoded demo accounts (buildathon scope) |

---

## Running it locally

**Backend**

```bash
pip install -r requirements.txt
cp .env.example .env        # add your own AI provider key(s); all optional
uvicorn api:app --host 127.0.0.1 --port 8001
```

Port 8001 matters — `frontend/vite.config.ts` proxies `/api` to it. If you
change the port, update the proxy target too, or the frontend will silently
talk to nothing.

At least one of `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY` should
be set for real AI investigation; with none set, cases stay honestly
`ai_pending` instead of getting a fabricated verdict.

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL and sign in with a demo account below.

**Demo accounts** (fake credentials, safe to share — not real secrets):

| Email | Password |
|---|---|
| demo@acmecorp.com | Lx7#Recon@2026Kq |
| demo@betastore.com | Lx7#Recon@2026Kq |
| demo@gammafoods.com | Lx7#Recon@2026Kq |
| demo@deltatech.com | Lx7#Recon@2026Kq |

Each backend restart clears active sessions (in-memory auth) — sign in again
after restarting `uvicorn`.

**Verifying the engine's accuracy yourself**

```bash
python validate_data.py       # scores engine.py output against ground_truth.csv
python -m pytest test_remittance.py -v   # 14 checks on the bulk-remittance join
```

---

## The demo data flow

Data unlocks in two batches (`data/orders.csv`, `data/settlements.csv`,
`data/remittances.csv`, all synthetic) to demonstrate incremental sync: click
**Sync & Reconcile** once for batch 1, and again once it's available for
batch 2. Reconciliation always runs over the *full* cumulative dataset, not
just the new batch — a COD order synced today may not get its bank credit
until batch 2, and re-scoring everything each time is what lets that resolve
correctly instead of showing as a false exception.

---

## Known limitations (by design, not oversight)

- **Synthetic dataset**, not a live merchant's data — built to exercise every
  case type the engine and AI layer handle, validated against a ground-truth
  file rather than "it looked right."
- **Razorpay Test Mode never produces real settlements** — no real money
  moves in test mode, so a live key here will correctly show zero gateway
  settlements. This is expected Razorpay behavior, not a Ledgr bug.
- **In-memory auth + JSON-file case storage** — correct and durable for a
  single-process demo (survives refresh, logout, restart), not a
  multi-user production store. The production path is the same schema on
  Postgres.
- **Split payouts** (one order paid across two settlements) and **late
  chargebacks** (reversing an already-cleared record weeks later) are not
  modeled — the inverse and the sequel of problems that are handled.
- **Bank/courier narration text** is carried and displayed, not parsed —
  formats vary per courier per bank with no reliable common structure.

Being explicit about these is deliberate: every one is a stated scope
boundary with a known fix, not a discovered gap.

---

## Project structure

```
engine.py            5-tier deterministic reconciliation, network-free
remittance.py         Bulk COD remittance join + checksum gate
case_engine.py         Case lifecycle, batched AI investigation, caching
ai_client.py            Multi-provider AI client (Groq/OpenRouter/Gemini)
state_store.py           Per-merchant persistent case/run state (JSON)
api.py                    FastAPI transport layer — 22 endpoints
auth.py                    Demo merchant accounts + bearer-token auth
razorpay_client.py          Real Razorpay Settlements API client
shopify_client.py            Mock merchant order source
gen_data.py                   Synthetic demo dataset generator
validate_data.py                Scores engine.py output against ground_truth.csv
test_remittance.py                Unit tests for the remittance join
config.py                          Shared constants (fee bands, tolerances)
frontend/                           React + TypeScript SPA
data/                                 Demo CSVs + ground_truth.csv + per-merchant state
```

---

## Credit

Built solo for the Razorpay Buildathon (Track 04 — AI Finance Controller),
2026.
