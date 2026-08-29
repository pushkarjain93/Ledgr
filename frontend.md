# Ledgr Frontend — Handoff Document

> AI-assisted payment reconciliation UI for the Razorpay Buildathon.  
> **Core principle:** this is a financial tool. **Never fabricate a number.**

---

## Stack & layout

| Layer | Tech |
|--------|------|
| UI | React 19 + TypeScript |
| Build | Vite 8 |
| Styling | Tailwind CSS 4 |
| Routing | react-router-dom v7 |
| API | Typed fetch client in `frontend/src/lib/api.ts` |

```
Ledgr/
├── api.py                 # FastAPI — orchestrates Python core (avoid changing engine logic from UI work)
├── engine.py, case_engine.py, state_store.py  # Python core (DO NOT MODIFY unless explicitly needed)
└── frontend/
    ├── public/favicon.svg
    └── src/
        ├── App.tsx, main.tsx, index.css
        ├── context/
        │   ├── AppContext.tsx      # Server state, auth, batch notification
        │   ├── ThemeContext.tsx    # Light / dark (localStorage)
        │   └── SidebarContext.tsx  # Collapsed sidebar (localStorage)
        ├── lib/
        │   ├── api.ts, money.ts, constants.ts
        │   ├── caseUtils.ts, caseDisplay.ts, caseQueue.ts
        │   ├── transactionDisplay.ts
        │   ├── reconciliationMetrics.ts, reconciliationFinancials.ts
        │   ├── dashboardMetrics.ts, merchantState.ts, sourceStatus.ts
        │   └── scrollAppMain.ts
        ├── types/case.ts
        ├── components/
        │   ├── LedgrLogo.tsx, icons.tsx
        │   ├── layout/         # AppShell, Sidebar, PageHeader, NewBatchOverlay, NavIcons
        │   ├── dashboard/      # StatsSegment, ReconciliationCharts, RecentActivity
        │   ├── reconciliation/ # SourceCards, ReconciliationResultsWorkspace, AiReviewQueue, CodAwaitingSettlementPanel, …
        │   ├── cases/          # CaseFilterBar, CasesTable, CaseSummaryPanel, CaseAiAnalysisPanel, CaseTimeline, …
        │   └── transactions/   # TransactionFilters, TransactionsTable, TransactionDetailDrawer
        └── pages/
            ├── LoginPage.tsx
            ├── DashboardPage.tsx
            ├── ReconciliationsPage.tsx
            ├── CasesPage.tsx
            ├── CaseDetailPage.tsx
            ├── TransactionsPage.tsx
            └── SettingsPage.tsx
```

### Running locally

**Terminal 1 — API** (use project venv; pin deps in `requirements.txt`):

```powershell
cd Ledgr
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn api:app --reload --port 8001
```

**Terminal 2 — Frontend:**

```powershell
cd Ledgr/frontend
npm install
npm run dev
# → http://127.0.0.1:5173
```

- Default API URL: same-origin `/api/*` (Vite dev proxy in `vite.config.ts` → `http://127.0.0.1:8001`).
- Override proxy: set `VITE_API_URL=http://localhost:8001` in `frontend/.env.local`.
- **Demo login:** `demo@acmecorp.com` / `demo123`

---

## Shell & navigation

### Sidebar (`layout/Sidebar.tsx`) — **Built**

| Route | Label |
|-------|--------|
| `/dashboard` | Dashboard |
| `/reconciliations` | Reconciliations |
| `/cases` | Cases |
| `/cases/:caseId` | Case detail (no sidebar item) |
| `/transactions` | Transactions |
| `/settings` | Settings |

**Also:** Help mailto link (`support@ledgr.ai`) at sidebar bottom.

**Collapsible sidebar** (`SidebarContext`): expanded 240px / collapsed 72px; persisted in `localStorage` (`ledgr_sidebar_collapsed`).

### Branding — **Built**

`LedgrLogo.tsx` + `public/favicon.svg`. Used on login and sidebar.

### Page header (`layout/PageHeader.tsx`) — **Built**

**Default variant** (Cases, Reconciliations, Transactions, Settings, Case detail):
- Single white bar: `{title}` left · bell · AI assistant · profile right

**Dashboard variant** (`variant="dashboard"`):
- Row 1: `Dashboard` · bell · AI · profile
- Row 2: `Welcome back! 👋` · **←** date **→** (`shiftISODate`, `max={today}`)

Profile menu: Settings, **Reset demo data**, Logout. AI assistant panel is a stub (“coming soon”).

### App shell scroll — **Built**

`AppShell.tsx` scrolls `[data-app-main]` to top on every route/search change (`scrollAppMain.ts`). Fixes mid-page landings when navigating from dashboard links.

### Theme — **Built**

`ThemeContext`: Light / Dark in Settings. Persists `ledgr_theme`, applies `html.dark`.

---

## API reference (frontend consumer)

All calls go through `src/lib/api.ts`. Money is **integer paise** everywhere.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/login` | `{ email, password }` → `{ token, merchant }` |
| POST | `/api/logout` | Clear session |
| GET | `/api/me` | Current merchant |
| GET | `/api/state` | Batch progress, runs, cases, `run_date`, notification flags |
| GET | `/api/sources` | Shopify / Razorpay / Bank status + counts |
| GET | `/api/settings` | Tolerance bands, COD windows, AI config |
| POST | `/api/reset` | Wipe merchant demo state |
| POST | `/api/sync-and-reconcile` | Run pipeline → `{ run, steps[], cases }` |
| GET | `/api/transactions` | All records incl. clean matches (+ `order_date`, `payment_mode`) |
| GET | `/api/cases` | `?case_status=` `?case_type=` |
| GET | `/api/cases/{id}` | Single case |
| POST | `/api/cases/{id}/resolve` | `{ resolution_type, comment }` |
| POST | `/api/cases/{id}/reopen` | `{ reason }` — mistaken resolution |
| POST | `/api/cases/{id}/bookmark` | Toggle bookmark |
| POST | `/api/cases/{id}/comment` | Save working comment |
| POST | `/api/cases/{id}/retry-ai` | Retry rate-limited AI |
| POST | `/api/cases/{id}/investigate-further` | One extra agentic AI step |
| POST | `/api/ask-ai` | `{ question, case_id?, history[] }` → `{ answer, source }` |
| GET | `/api/cases/{id}/evidence` | Real order / settlement / fee-band records behind a case |
| GET | `/api/cases/{id}/message-options` | Who it makes sense to contact, from the case's own facts |
| POST | `/api/cases/{id}/draft-message` | `{ recipient_type }` → drafted subject + body (**never sends**) |
| GET | `/api/health` | Health check |

Auth: Bearer token in `localStorage` key `ledgr_token`.

---

## Domain rules (must get right)

### Case status — never merge visually

| Status | Meaning |
|--------|---------|
| `pending_settlement` | Normal COD window; not broken yet |
| `needs_ai` | Queued for batched AI (internal; may not appear long) |
| `ai_pending` | AI not completed yet (often rate limit) |
| `ai_recommendation` | AI suggests resolving — human confirms |
| `manual_review` | AI investigated; human must decide |
| `exception` | No AI path |
| `resolved` | Closed |

**`ai_pending` ≠ `manual_review`.** One means AI hasn't run; the other means AI ran and wants a human.

### COD awaiting settlement (14-day rule)

Constants: `COD_WARN_DAYS = 14` in `constants.ts`.

- COD orders **inside** the 0–14 day window are **informational only** — shown in Reconciliations `CodAwaitingSettlementPanel`, **excluded** from Cases review queue, dashboard open counts, and AI review queue.
- After 14 days → `R2_REMITTANCE_OVERDUE` exception enters case review.
- Helpers: `isAwaitingSettlementCase`, `isWithinCodSettlementWindow`, `isOpenForReview` in `caseUtils.ts`.

### AI providers — failover chain

Three providers, tried in order: **Gemini → OpenRouter → Groq** (`ai_client.PROVIDER_ORDER`).
Each is a separate account with independent limits — genuine resilience, not quota
farming. A provider with no key is skipped silently.

- If **every** provider fails, cases still land on `ai_pending` and Ask AI falls
  back to the deterministic answerer. Failover adds capacity; it never removes
  the honesty path.
- Each AI verdict records the `provider` that produced it — models calibrate
  confidence differently, so an unattributed 80% is not auditable.
- `GET /api/settings` exposes `ai_providers` so the UI can show what's active.
- Ask AI answers show which provider replied ("Answered by AI (openrouter)"), or
  "AI unavailable — answered directly from your data" on the Python fallback.

### Money & confidence

- Amounts: **integer paise** → display with `formatINR()` from `lib/money.ts`.
- Confidence: use `displayConfidence()` / `confidenceTier()` — returns `"Pending"`, `"—"`, or `"N%"`. **Never show 0% when null.**
- Aging: `caseAgeDays()` / `formatAge()` — **currently** uses hardcoded `RUN_DATE` in `constants.ts` (`2026-09-01`). API returns `run_date` but it is **not yet wired** into AppContext (see remaining work).

### Resolving cases

- `manual_review` resolution **requires a comment** (server 400 without one).
- `accepted` may auto-fill comment from AI `next_step`.
- `auto_resolved` cases cannot be reopened.

### Sync UX — intentional design

- Reconciliation runs **only on user click** (Sync & Reconcile). **No** live auto-sync per order, **no** SSE/WebSocket streaming, **no** background reconcile on every arrival.
- New data arrives as **batches**; bell notifies once. User chooses when to sync.
- After sync completes, steps/results render from the **completed** API response (button shows loading state only).

### Charts & metrics — honest limits

- **No fabricated history:** no sparklines, “vs last month”, or forecasts unless data exists in API responses.
- **AI contribution %** on dashboard = `ai_resolved / total_records` from each run (engine `ai_assisted` bucket). Not the same as “cases Gemini investigated” — label honestly.
- **Ask AI now routes every question to a model.** The old Python-keyword-first
  path was removed from the primary route after it confidently answered the wrong
  question; it survives only as a fallback when all providers are exhausted.
- **Reconciliation trend chart** needs data in the selected period; otherwise empty state.

---

## State

### AppContext (`useApp()`)

| Field | Source | Notes |
|-------|--------|-------|
| `merchant` | `/api/me`, login | Session identity |
| `state` | `/api/state` | **Date-filtered** — runs filtered by `selectedDate` |
| `cases` | derived from `state.cases` | All cases (not date-filtered) |
| `dashboard` | `computeDashboardMetrics(state)` | Open / needs-decision counts |
| `hasNewBatch` | `batch_available` + unreconciled batch | Bell red dot |
| `allRuns` | `reconciliation_runs` (unfiltered) | Charts + Reconciliations history |
| `batchAvailable` | maps from `batch_available` | Sync button enable |
| `currentBatch` | `/api/state` | Batch panel copy |
| `nextBatchAvailableAt` | `/api/state` | Waiting message; polled refresh |
| `totalBatches` | `constants.TOTAL_BATCHES` (2) | Batch X of Y |
| `lastSyncAt` | latest run timestamp | Settings + Reconciliations |
| `selectedDate` | local | ISO date; filters dashboard runs only |
| `refresh()` | `GET /api/state` | Call after any mutation |
| `resetDemoData()` | `POST /api/reset` + refresh | Profile menu |
| `login` / `logout` | API + token | |
| `loading` / `error` | bootstrap | |

**Not in context (call `api.*` directly):** transactions, sources, settings, sync, case detail fetch, case mutations, ask-ai.

**Persisted locally:** auth token, theme, sidebar collapsed. Financial state is never cached in localStorage.

### Batch notification behaviour

- When a batch is available and unreconciled → **red dot** on bell + auto-open **popover** below bell.
- **× / Later / click outside** → hides popover only; notification **stays** until batch is reconciled.
- **Reconcile now** → navigates to `/reconciliations`.
- Popover reopens when user clicks bell.
- `notification_seen` from server is **not** updated by frontend yet (dismiss is local UI only).

---

## Screens

### Login (`/login`) — **Built**

Email/password, demo account shortcut, validation, `ApiError` banner. **Complete.**

---

### Dashboard (`/dashboard`) — **Built (v1)**

**Shows:**
- Header (dashboard variant + date nav)
- Sync & Reconcile CTA → `/reconciliations`
- **Stats row** (5 KPIs): runs, records, AI contribution %, open cases, needs decision — links to Cases
- **Reconciliation trend** — **line chart** with Day / Month / Year period selector (`ReconciliationChart`)
- **Manual work eliminated** card (`ManualWorkEliminatedCard`)
- **Recent activity** — runs for selected date

**Date filtering:** `selectedDate` filters `reconciliation_runs` only. Cases are **not** date-filtered.

**Open case counts** use `isOpenForReview()` — excludes in-window COD awaiting settlement.

**Status:** Functional. Empty state before first run.

---

### Reconciliations (`/reconciliations`) — **Built (v1)**

**Shows:**
- **Sync panel** — status copy (ready / waiting / all done), last sync, **Sync & Reconcile** button
- After ≥1 run: **ReconciliationResultsWorkspace**
  - Summary boxes, financial health, outcome funnel
  - **COD awaiting settlement** collapsible panel (informational, read-only)
  - **AI review queue** (compact table → case detail)
- **Run history** table (`RunHistoryTable`)

**Behaviour:**
- Sync is **manual only**; button disabled while `syncing`; results appear after API returns
- 409 / no new data → inline notice (not an error toast)
- `POST /api/sync-and-reconcile` → `refresh()` + reload transactions/cases for workspace

**Status:** Functional v1.

---

### Cases (`/cases`) — **Built (v1)**

**Purpose:** AI review queue — open cases needing human attention.

**Shows:**
- Filter pills (URL `?filter=`):
  - All open · Needs your decision · Waiting on AI · Bookmarked · Resolved
- Table: order ID (+ customer), expected/received, AI confidence, recommendation, status, Review link
- Row → `/cases/:caseId?filter=…`

**Filtering:** Uses `filterCases()` in `caseQueue.ts`. Default “All open” excludes resolved cases and **excludes in-window COD** (`isOpenForReview`). No separate “Awaiting settlement” tab — those live on Reconciliations only.

**Status:** Built (v1).

---

### Case detail (`/cases/:caseId`) — **Built (v1, partial actions)**

**Shows:**
- Prev/next nav within current filter queue
- **Summary** — order/settlement IDs, amounts (INR), reason, customer, dates
- **AI analysis** — finding, evidence, recommendation, confidence, errors
- **Supporting documents** — anchor links to sections (not real file uploads)
- **Timeline** — from `case.history[]`
- **Actions (wired):** Accept recommendation, Resolve manually (comment required), Bookmark, **Reopen** (resolved cases, not `auto_resolved`)

**Actions (API exists, UI not wired yet):**
- Ask AI (`POST /api/ask-ai`)
- Investigate further
- Save standalone comment (`POST /api/cases/{id}/comment`)
- Retry AI for `ai_pending`

**Status:** Built for core resolve flow; advanced AI actions remain.

---

### Transactions (`/transactions`) — **Built (v1)**

**Purpose:** Searchable ledger of **every** reconciled record (including auto-matches).

**Shows:**
- Search (record ID, settlement, reason, …)
- Filters: **date** (single day, clearable), **payment mode**, **status** (Matched / AI review / Awaiting settlement / Exception)
- Table: record ID, tier, expected/received/delta, status badge, details (eye)
- **Detail drawer** — amounts, order date, payment mode, reconciliation fields, **View case** when linked case is `isOpenForReview` (not in-window COD)

**Data:** `GET /api/transactions` — requires ≥1 reconciliation run; returns `order_date`, `payment_mode` per record.

**Not built (deferred):** CSV export, date range filter, customer/source columns in table.

**Status:** Built (v1).

---

### Settings (`/settings`) — **Built (v1)**

Accordion: Data sources, Last sync, Security (placeholder), Theme, Send feedback (mailto).

**Note:** No standalone Reports or Data Sources pages — sources live here. Demo reset is in **profile menu**, not Settings.

**Status:** Complete (v1).

---

## User flows

### 1. Login

1. `/login` → credentials or demo shortcut
2. `POST /api/login` → token → `refresh()`
3. Redirect to `/dashboard`

### 2. First reconciliation

1. Dashboard empty; bell shows batch 1 waiting
2. **Reconciliations** → **Sync & Reconcile**
3. Engine + batched AI run; `refresh()` populates dashboard and cases
4. Bell clears when batch reconciled

### 3. Batch 2 arrives (~45s demo delay)

1. AppContext polls `next_batch_available_at`; auto-refresh when timer passes
2. Bell + popover; user may dismiss popover locally
3. User manually syncs batch 2 when ready
4. Some batch-1 pending-settlement cases may auto-resolve

### 4. Resolve a case

1. Cases → “Needs your decision” (or Reconciliations AI queue)
2. Open case ticket
3. **Accept** → `POST resolve { resolution_type: 'accepted' }`
4. **Manual review** → comment required → `{ resolution_type: 'manual_review', comment }`
5. **Reopen** (if resolved by mistake) → reason required → `POST /api/cases/{id}/reopen`
6. `refresh()` updates counts

### 5. Browse transactions

1. After ≥1 sync, **Transactions** loads full ledger
2. Filter by date / payment mode / status; open drawer for details
3. **View case** only when case is in open review (not in-window COD)

### 6. Reset demo

1. Profile menu → Reset demo data
2. `POST /api/reset` → fresh merchant JSON
3. Dashboard empty; batch 1 available again

---

## Shared components (selected)

### Layout

| Component | File | Role |
|-----------|------|------|
| `AppShell` | `layout/AppShell.tsx` | Sidebar + header + scroll-to-top on navigation |
| `PageHeader` | `layout/PageHeader.tsx` | Bell, AI stub, profile, dashboard date nav |
| `BellBatchPopover` | `layout/NewBatchOverlay.tsx` | New batch popover → Reconciliations |

### Cases

| Component | Role |
|-----------|------|
| `CaseFilterBar` | URL filter pills |
| `CasesTable` | Review queue table |
| `CaseSummaryPanel` / `CaseAiAnalysisPanel` / `CaseTimeline` | Case detail sections |
| `CaseDetailNav` | Prev/next in filtered queue |

### Reconciliations

| Component | Role |
|-----------|------|
| `ReconciliationResultsWorkspace` | Post-sync KPI workspace |
| `CodAwaitingSettlementPanel` | In-window COD list (informational) |
| `AiReviewQueue` | Compact open-case table |
| `RunHistoryTable` | All runs |

### Transactions

| Component | Role |
|-----------|------|
| `TransactionFiltersBar` | Search + date + payment mode + status |
| `TransactionsTable` | Ledger table |
| `TransactionDetailDrawer` | Right-side detail panel |

### Lib helpers

| Module | Key exports |
|--------|-------------|
| `api.ts` | `api`, `ApiError`, all response types |
| `money.ts` | `formatINR`, `formatCompactINR` |
| `caseUtils.ts` | `isOpenForReview`, `isAwaitingSettlementCase`, `caseAgeDays`, `canReopenCase`, … |
| `caseQueue.ts` | `filterCases`, `caseDetailPath`, `awaitingSettlementCases` |
| `transactionDisplay.ts` | `transactionUiStatus`, `filterTransactions`, status badges |
| `reconciliationMetrics.ts` | `buildReconciliationGraphSeries`, `computeReconciliationDashboard` |
| `reconciliationFinancials.ts` | `buildReconciliationViewModel` |
| `merchantState.ts` | `stateForSelectedDate`, `todayISO`, `shiftISODate`, period helpers |
| `constants.ts` | `RUN_DATE`, `COD_WARN_DAYS`, `TOTAL_BATCHES` |

---

## Remaining frontend work

Prioritized gaps — **not** blockers for a demo of login → sync → review → resolve → transactions.

### P1 — Case detail actions (API ready)

| Feature | Endpoint | Status |
|---------|----------|--------|
| Ask AI panel | `POST /api/ask-ai` | ✅ **Built** — global (header) + case-scoped, with conversation history |
| Supporting Documents | `GET …/evidence` | ✅ **Built** — modals with real order/settlement/fee records |
| Draft a message | `POST …/draft-message` | ✅ **Built** — courier / gateway / customer; Ledgr never sends |
| Investigate further | `POST …/investigate-further` | ❌ **Not wired** — API ready, no UI calls it |
| Retry AI | `POST …/retry-ai` | ❌ **Not wired** — needed for `ai_pending` cases |
| Standalone comment | `POST …/comment` | ❌ **Not wired** — save without resolving |
| Settings from API | `GET /api/settings` | ❌ **Not wired** — real tolerance bands + AI config unused |

### P2 — Wiring & polish

| Item | Notes |
|------|-------|
| Wire `run_date` from `/api/state` | Replace hardcoded `RUN_DATE` in `caseAgeDays()` |
| Persist bell dismiss | Optional backend routes for `notification_seen` |
| Transactions export CSV | Client-side from filtered records |
| Transactions date range | Extend single-day filter |
| Table columns | Customer, source on transactions (needs API fields) |
| `frontend.md` bell copy | Popover still says “Batch X” — could soften to “New data” |

### P3 — Out of scope / explicitly rejected

| Item | Decision |
|------|----------|
| Live SSE sync steps | **Not planned** — harms UX; sync stays on-demand |
| Auto-sync per new order | **Not planned** — batch + manual sync only |
| Reports page | Not in React router (existed in Streamlit) |
| Real supporting documents | Anchor links only for now |

---

## NEEDS BACKEND (optional / if gaps appear)

### 1. Notification lifecycle endpoints (optional)

`state_store.py` has helpers but no API routes. Frontend derives bell from `batch_available`.

```
POST /api/notifications/dismiss-overlay
POST /api/notifications/mark-read
```

### 2. `run_date` in AppContext

Returned by `/api/state`; frontend should consume it for aging instead of `constants.RUN_DATE`.

### 3. Transactions ledger persistence (if discrepancies)

`GET /api/transactions` re-runs engine over all batches. At scale, persist ledger at sync time.

### 4. Extra transaction fields (for table parity)

Customer name, source channel, settled-on timestamp — join from orders/settlements in API if needed.

---

## Build status summary

| Area | Status |
|------|--------|
| Login | ✅ Built |
| Shell (sidebar, header, bell, theme, scroll) | ✅ Built |
| Dashboard | ✅ Built (v1) — line trend chart, date nav |
| Reconciliations | ✅ Built (v1) — COD panel, AI queue, run history |
| Cases list | ✅ Built (v1) |
| Case detail | ✅ Built (v2) — resolve, bookmark, reopen, **Ask AI, Supporting Documents, Draft message**; investigate-further / retry / standalone-comment **still pending** |
| Transactions | ✅ Built (v1) — date, payment mode, status filters |
| Settings | ✅ Built (v1) |

**Demo-ready path:** Login → Reconcile → Review cases → Resolve → Transactions.

**Overall: ~70% complete.** Remaining engineering is ~5 hours; the larger
remaining risk is that **no clean end-to-end rehearsal has ever been run** —
verification so far has been piecemeal, sometimes against a rate-limited
provider or a stale server process.

---

## Open questions / assumptions

1. **`run_date` wiring** — Should dashboard `selectedDate` also filter cases? Currently cases are global; only runs are date-filtered.

2. **AI contribution metric** — Run-level `ai_resolved / total_records` vs case-level “Gemini investigated” — confirm product copy.

3. **Dev proxy port** — `vite.config.ts` proxies to **8001**. Production uses `VITE_API_URL`.

4. **Case detail AI chat** — Global header stub vs case-scoped Ask AI panel — scope TBD.

5. **Dashboard date nav** — Cannot select past today. No lower bound on previous day.

6. **Responsive** — Wide tables scroll inside containers; charts scroll horizontally on narrow viewports.

---

## Hard rules (checklist for every PR)

1. Never invent data — if an endpoint doesn't provide it, show empty / “Not enough data yet”.
2. Never merge `ai_pending` and `manual_review` in UI.
3. Money in paise; display via `formatINR` only.
4. Confidence null → “Pending” or “—”, never fake percentages.
5. Disabled buttons must look disabled.
6. No horizontal page scroll; wide tables scroll inside their container.
7. In-window COD is informational — never count as open review or show “View case” from transactions.

---

*Last updated: Aug 30, 2026 (evening) — backend fully wired via `api.py` (22 endpoints);
multi-provider AI failover (Gemini → OpenRouter → Groq); Ask AI live (global + case-scoped,
with conversation history); Supporting Documents open real records; AI message drafting
(never sends); cases sorted by AI confidence descending. Fixed: deep-link/refresh redirect
to /dashboard, AI prioritising by `delta` instead of `amount_at_risk`, raw paise in drafted
messages. Still unwired: investigate-further, retry-AI, standalone comment, settings.*
