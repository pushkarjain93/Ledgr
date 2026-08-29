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
├── api.py                 # FastAPI — 17 endpoints (DO NOT MODIFY from frontend work)
├── engine.py, case_engine.py, state_store.py  # Python core (DO NOT MODIFY)
└── frontend/
    ├── public/favicon.svg # Matches LedgrLogo mark
    └── src/
        ├── App.tsx, main.tsx, index.css
        ├── context/
        │   ├── AppContext.tsx      # Server state, auth, batch notification
        │   ├── ThemeContext.tsx    # Light / dark (localStorage)
        │   └── SidebarContext.tsx  # Collapsed sidebar (localStorage)
        ├── lib/           # api, caseUtils, money, metrics, merchantState, sourceStatus
        ├── types/case.ts
        ├── components/
        │   ├── LedgrLogo.tsx
        │   ├── layout/         # AppShell, Sidebar, PageHeader, NewBatchOverlay
        │   ├── dashboard/      # StatsSegment, ReconciliationCharts, RecentActivity
        │   └── reconciliation/ # SourceCards, SyncSteps, RunHistoryTable
        └── pages/              # Login, Dashboard, Settings, Reconciliations (built); Cases, Transactions (stub)
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
- If port 8000 is free, run uvicorn on 8000 and change the proxy target in `vite.config.ts` to match.
- Override proxy: set `VITE_API_URL=http://localhost:8001` in `frontend/.env.local`.
- **Demo login:** `demo@acmecorp.com` / `demo123`

---

## Shell & navigation

### Sidebar (`layout/Sidebar.tsx`) — **Built**

| Route | Label | Icon |
|-------|--------|------|
| `/dashboard` | Dashboard | 📊 |
| `/reconciliations` | Reconciliations | 🔁 |
| `/cases` | Cases | 📋 |
| `/cases/:caseId` | Case detail (no sidebar item) | — |
| `/transactions` | Transactions | 💳 |
| `/settings` | Settings | ⚙️ |

**Also:** Help mailto link (`support@ledgr.ai`) at sidebar bottom.

**Collapsible sidebar** (`SidebarContext`):
- Expanded: 240px — logo + wordmark, emoji + labels, merchant name on toggle row
- Collapsed: 72px — icon-only nav; logo mark only (no wordmark)
- Toggle: full row below logo (merchant name + ☰ icon); state persisted in `localStorage` (`ledgr_sidebar_collapsed`)

### Branding — **Built**

`LedgrLogo.tsx` + `public/favicon.svg`: minimal blue rounded square with ledger spine + three entry lines. Props: `size?: 'sm' | 'md'`, `showWordmark?: boolean`. Used on login and sidebar.

### Page header (`layout/PageHeader.tsx`) — **Built**

Rendered from `AppShell` for **all** routes (including Dashboard).

**Default variant** (Cases, Reconciliations, Transactions, Settings, Case detail):
- Single white bar with bottom border: `{title}` left · bell · AI assistant · profile right

**Dashboard variant** (`variant="dashboard"`):
- **Row 1 (white bg, border below):** `Dashboard` · bell · AI assistant · profile
- **Row 2 (page grey bg, no border):** `Welcome back! 👋` (28–32px) left · date controls right
  - **←** previous day · calendar + date input · **→** next day
  - **→** disabled when `selectedDate >= today` (`todayISO()`); date input `max={today}`
  - Day step via `shiftISODate()` in `merchantState.ts`

Profile menu: Settings link, Reset demo data, Logout. AI assistant panel is a stub message.

### Theme — **Built**

`ThemeContext`: Light / Dark toggle in Settings. Persists `ledgr_theme` in `localStorage`, applies `html.dark`. Dark mode styles on shell, sidebar, header, Settings; dashboard cards/charts partially styled.

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
| GET | `/api/transactions` | All records incl. clean matches |
| GET | `/api/cases` | `?case_status=` `?case_type=` |
| GET | `/api/cases/{id}` | Single case |
| POST | `/api/cases/{id}/resolve` | `{ resolution_type, comment }` |
| POST | `/api/cases/{id}/bookmark` | Toggle bookmark |
| POST | `/api/cases/{id}/comment` | Save working comment |
| POST | `/api/cases/{id}/retry-ai` | Retry rate-limited AI |
| POST | `/api/cases/{id}/investigate-further` | One extra agentic AI step |
| POST | `/api/ask-ai` | `{ question, case_id? }` → `{ answer, source }` |

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

### Money & confidence

- Amounts: **integer paise** → display with `formatINR()` from `lib/money.ts`.
- Confidence: use `displayConfidence()` from `lib/caseUtils.ts` — returns `"Pending"`, `"—"`, or `"N%"`. **Never show 0% when null.**
- Aging: use `caseAgeDays()` / `formatAge()` measured against **`run_date` from API** (not browser clock). See open questions — `run_date` is returned by `/api/state` but not yet wired into context.

### Resolving cases

- `manual_review` resolution **requires a comment** (server 400 without one).
- `accepted` may auto-fill comment from AI `next_step`.

### Charts & metrics — honest limits

- **No fabricated history:** no sparklines, “vs last month”, or forecasts unless data exists in API responses.
- **AI contribution %** on dashboard = `ai_resolved / total_records` from each run (engine `ai_assisted` bucket). Not the same as “cases Gemini investigated” — label honestly.
- **AI contribution chart** needs ≥2 runs on the selected date; otherwise show “Not enough data yet”.

---

## State

### AppContext (`useApp()`)

| Field | Source | Notes |
|-------|--------|-------|
| `merchant` | `/api/me`, login | Session identity |
| `state` | `/api/state` | **Date-filtered** — runs filtered by `selectedDate` |
| `cases` | derived from `state.cases` | Open case list for selected date context |
| `dashboard` | `computeDashboardMetrics(state)` | `needsDecisionCount` today |
| `hasNewBatch` | `batch_available` + unreconciled batch | Drives bell red dot until batch reconciled |
| `allRuns` | `reconciliation_runs` (unfiltered) | Reconciliations run history |
| `batchAvailable` | maps from `batch_available` | Sync button enable |
| `currentBatch` | `/api/state` | Batch panel copy |
| `nextBatchAvailableAt` | `/api/state` | Waiting-for-batch message; polled refresh |
| `totalBatches` | `constants.TOTAL_BATCHES` (2) | Batch X of Y |
| `lastSyncAt` | latest `reconciliation_runs[0].timestamp` | Settings + Reconciliations |
| `selectedDate` | local | ISO date string; filters dashboard runs |
| `setSelectedDate` | local | |
| `refresh()` | `GET /api/state` | Call after any mutation |
| `resetDemoData()` | `POST /api/reset` + refresh | |
| `login` / `logout` | API + token | |
| `loading` / `error` | bootstrap | |

**Not in context (call `api.*` directly):** transactions, sources, settings, sync, case mutations, ask-ai.

**Persisted locally:** auth token (`ledgr_token`), theme (`ledgr_theme`), sidebar collapsed (`ledgr_sidebar_collapsed`). Financial state is never cached in localStorage.

### ThemeContext (`useTheme()`)

| Field | Notes |
|-------|--------|
| `theme` | `'light' \| 'dark'` |
| `setTheme` | Updates DOM + localStorage |

### SidebarContext (`useSidebar()`)

| Field | Notes |
|-------|--------|
| `collapsed` | Sidebar narrow mode |
| `toggleCollapsed` | Flip + persist |

### Local component state (examples)

| Component | Local state |
|-----------|-------------|
| `PageHeader` | Profile menu, AI panel, bell popover; dashboard date nav |
| `ReconciliationsPage` | sources fetch, sync in progress, last sync result steps |
| `ReconciliationChart` | Selected/hovered bar |
| `LoginPage` | Form fields, validation errors |

### Batch notification behaviour

- When a batch is available and unreconciled → **red dot** on bell + auto-open **popover** below bell.
- **× / Later / click outside** → hides popover only; notification **stays** until batch is reconciled.
- **Reconcile now** → navigates to `/reconciliations` (does not clear notification).
- Popover reopens when user clicks bell.

---

## Screens

### Login (`/login`) — **Built**

**Purpose:** Authenticate demo merchants against `auth.py` via API.

**Shows:**
- Ledgr logo + wordmark, sign-in card on gradient background
- Email/password fields with validation, show/hide password, remember-me checkbox
- “Try demo account” fills `demo@acmecorp.com` / `demo123`
- Inline field errors + API error banner (connectivity / bad credentials surfaced from `ApiError`)

**Data:** `POST /api/login`, `useApp().login()`.

**Status:** Complete.

---

### Dashboard (`/dashboard`) — **Built (v1)**

**Purpose:** Command center — batch status, run metrics, case counts, charts for selected date.

**Shows:**
- **Header** — see [Page header](#page-header-layoutpageheadertsx--built) (dashboard variant: welcome row + date nav)
- Sync & Reconcile CTA card → `/reconciliations`
- **Stats row** (5 KPI cards): total runs, records processed, AI contribution % (latest run), open cases, needs decision — last two link to `/cases`
- **Reconciliation by run** — bar chart, clickable bars
- **AI contribution** — compares latest vs previous run on selected date (needs ≥2 runs; otherwise empty state)
- **Recent activity** — run history list for selected date

**Date filtering:** `selectedDate` filters `reconciliation_runs` only (via `stateForSelectedDate`). Cases list is **not** date-filtered yet.

**Data consumed:**

| Data | Source |
|------|--------|
| `reconciliation_runs` | `useApp().state` (date-filtered) |
| Cases / counts | `useApp().cases`, `dashboard` |
| Batch pending | `useApp().hasNewBatch` |
| Chart aggregates | `computeReconciliationDashboard()` in `lib/reconciliationMetrics.ts` |

**Status:** Functional for post-reconcile data. Empty state before first run.

---

### Reconciliations (`/reconciliations`) — **Built (v1)**

**Purpose:** Run Sync & Reconcile, show step progress, list all past runs.

**Shows:**
- **Batch panel** — batch X of Y, status (ready / scheduled / all done), last sync time, **Sync & Reconcile** button
- **Success banner** after sync — processed / auto matched / AI resolved / exceptions + link to Cases
- **Data sources** — 3 cards from `GET /api/sources` (`SourceCards.tsx`)
- **Pipeline steps** — step list from last sync response (`SyncSteps.tsx`); spinner while running
- **Run history** — full table, all runs unfiltered (`RunHistoryTable.tsx` + `useApp().allRuns`)

**Behaviour:**
- Button disabled when `!batchAvailable`, syncing, or all batches done
- `POST /api/sync-and-reconcile` → `refresh()` + reload sources; 409 surfaced as error
- Steps render from completed API response (not live SSE)

**Data consumed:**

| Data | Source |
|------|--------|
| Source status | `GET /api/sources` (page-local fetch) |
| Batch state | `useApp()` — `batchAvailable`, `currentBatch`, `nextBatchAvailableAt`, `totalBatches` |
| Run pipeline | `POST /api/sync-and-reconcile` |
| Past runs | `useApp().allRuns` |

**Status:** Functional v1 — user may request UX polish.

---

### Cases (`/cases`) — **Stub (filter logic only)**

**Purpose:** Review queue — all open reconciliation cases.

**Planned shows:**
- Filter tabs or URL params: all / needs decision / AI pending / awaiting settlement
- Sortable table: customer, type, amount at risk, age, confidence, status
- Row → `/cases/:caseId`

**Current:** Reads `useApp().cases`, supports `?filter=needs_decision|ai_pending|pending_settlement`. Count only — no table UI.

**Data needed:**

| Data | Endpoint |
|------|----------|
| Case list | `useApp().cases` or `GET /api/cases?case_status=` |

**Status:** Stub.

---

### Case detail (`/cases/:caseId`) — **Stub**

**Purpose:** Single case ticket — evidence, AI block, timeline, human resolve actions.

**Planned shows:**
- Order/settlement IDs, amounts (paise → INR), reason, explanation
- AI: confidence (`displayConfidence`), reason, next_step, error if `ai_pending`
- Actions: Accept recommendation, Keep for manual review (comment required), Retry AI, Investigate further
- Comment field, bookmark toggle
- Timeline from case `history[]`

**Data needed:**

| Data | Endpoint |
|------|----------|
| Case | `GET /api/cases/{id}` or from context |
| Mutations | resolve, comment, bookmark, retry-ai, investigate-further |

**Current:** Back link to `/cases`, resolves case id from URL via `useApp().cases`. Placeholder body only.

**Status:** Stub.

---

### Transactions (`/transactions`) — **Stub**

**Purpose:** Searchable ledger of **every** reconciled record (including clean auto-matches).

**Planned shows:**
- Filter by status, tier, batch; search by record ID
- Columns: record, tier, status, expected/received/delta (INR), case link if any

**Data needed:**

| Data | Endpoint |
|------|----------|
| All records | `GET /api/transactions` → `{ records[], total }` |

**Note:** Requires at least one completed reconciliation run; empty array before first sync.

**Status:** Stub.

---

### Settings (`/settings`) — **Built**

**Purpose:** Workspace preferences, data source visibility, theme, feedback.

**Shows:** Accordion sections (click heading to expand; one panel open at a time style via toggle):

- **Data sources** — Shopify (orders), Razorpay (settlements), Bank (COD) cards from `GET /api/sources`; connection status via `sourceStatus.ts` (`Connected`, `Demo data`, `Connection error`)
- **Last sync** — `formatLastSync(lastSyncAt)` from AppContext; “Not synced yet” before first run (not fabricated per-source times)
- **Security** — placeholder “Manage security” button
- **Theme** — Light / Dark segmented control (`ThemeContext`)
- **Send feedback** — mailto button

**Data consumed:**

| Data | Endpoint / source |
|------|-------------------|
| Source status | `GET /api/sources` |
| Last sync | `useApp().lastSyncAt` (from latest `reconciliation_runs[0]`) |
| Theme | `ThemeContext` (local) |

**Status:** Complete (v1).

---

## User flows

### 1. Login

1. User opens `/login`
2. Enters credentials or clicks “Try demo account”
3. `POST /api/login` → token stored → `refresh()` loads state
4. Redirect to `/dashboard`

### 2. First reconciliation (demo)

1. Dashboard empty; bell shows batch 1 waiting (popover below bell)
2. User goes to **Reconciliations** → **Sync & Reconcile**
3. `POST /api/sync-and-reconcile` runs engine + batched AI
4. `refresh()` → dashboard populates stats/charts; cases appear
5. Bell clears when batch no longer `batch_available`

### 3. Batch 2 arrives (~45s demo delay)

1. AppContext polls `next_batch_available_at`; auto-refresh when timer passes
2. Bell red dot + popover; user may close popover (notification persists)
3. Repeat sync for batch 2
4. Some batch-1 pending-settlement cases may auto-resolve

### 4. Resolve a case (planned)

1. Cases → filter “Needs your decision”
2. Open case ticket
3. Review AI recommendation + confidence
4. **Accept** → `POST resolve { resolution_type: 'accepted' }`
5. **Manual review** → require comment → `{ resolution_type: 'manual_review', comment }`
6. `refresh()` updates dashboard counts

### 5. Reset demo

1. Profile menu → Reset demo data
2. `POST /api/reset` → fresh merchant JSON
3. Dashboard returns to empty; batch 1 available again

---

## Shared components

### Layout

| Component | File | Props / role |
|-----------|------|----------------|
| `AppShell` | `layout/AppShell.tsx` | `SidebarProvider` + sidebar + `PageHeader` for every route; dashboard gets `variant="dashboard"` |
| `Sidebar` | `layout/Sidebar.tsx` | Collapsible nav, emoji icons, merchant toggle row, Help mailto |
| `PageHeader` | `layout/PageHeader.tsx` | `title`, `variant?: 'default' \| 'dashboard'` — bell, AI stub, profile; dashboard adds welcome row + date nav |
| `BellBatchPopover` | `layout/NewBatchOverlay.tsx` | `batchNum`, `onClose` — popover below bell; “Reconcile now” → `/reconciliations` |
| `BellEmptyPopover` | `layout/NewBatchOverlay.tsx` | `onClose` — when no pending batch |
| `ProtectedRoute` | `ProtectedRoute.tsx` | Redirects to `/login` if no merchant |
| `LedgrLogo` | `LedgrLogo.tsx` | `size?: 'sm' \| 'md'`, `showWordmark?`; exports `LedgrMarkIcon` |

### Reconciliations

| Component | File | Role |
|-----------|------|------|
| `SourceCards` | `reconciliation/SourceCards.tsx` | 3-column source status grid |
| `SyncSteps` | `reconciliation/SyncSteps.tsx` | Pipeline step list after sync |
| `RunHistoryTable` | `reconciliation/RunHistoryTable.tsx` | All runs table + link to Cases |

### Dashboard

| Component | Props | Role |
|-----------|-------|------|
| `StatsSegment` | `recon`, `needsDecisionCount`, `openCasesCount` | 5 KPI cards with links to Cases |
| `ReconciliationChart` | `runs: RunChartPoint[]` | Bar chart of records per run |
| `ImprovementChart` | `latest`, `previous`, `aiContributionDelta` | **AI contribution** chart — latest vs previous run % |
| `RecentActivity` | `runs` | Run history list |

### Lib helpers

| Module | Key exports |
|--------|-------------|
| `api.ts` | `api`, `ApiError`, `getToken`, all response types |
| `money.ts` | `formatINR(paise)`, `formatINRCompact` |
| `caseUtils.ts` | `isUnresolved`, `needsHumanDecision`, `displayConfidence`, `formatAge`, `issueTypeLabel`, … |
| `reconciliationMetrics.ts` | `computeReconciliationDashboard`, `parseRun`, `RunChartPoint` |
| `dashboardMetrics.ts` | `computeDashboardMetrics`, `listCases` |
| `merchantState.ts` | `hasPendingBatch`, `stateForSelectedDate`, `formatDisplayDate`, `todayISO`, `shiftISODate` |
| `sourceStatus.ts` | `sourceConnectionLabel`, `formatLastSync`, `SOURCE_ROWS` |
| `constants.ts` | `RUN_DATE`, `TOTAL_BATCHES`, `ISSUE_TYPE_LABELS`, demo merchant |

---

## NEEDS BACKEND

Items the frontend will need that are **missing or incomplete** in the current API/types:

### 1. Notification lifecycle endpoints (optional)

`state_store.py` has `mark_notification_read`, `dismiss_overlay`, `mark_notification_created`, but **no API routes**. Frontend currently derives bell state from `batch_available` only.

**Suggested shape:**

```
POST /api/notifications/dismiss-overlay   # hide popover, keep red dot
POST /api/notifications/mark-read         # clear red dot after reconcile CTA
```

### 2. `run_date` in AppContext

`GET /api/state` returns `run_date` (ISO). Frontend `Case` aging still defaults to hardcoded `RUN_DATE` in `constants.ts`. Should map API `run_date` into context and pass to `caseAgeDays(case, runDate)`.

### 3. Case `history` on frontend type

Backend cases include `history: [{ at, event }]`. `types/case.ts` does not declare it — needed for case ticket timeline.

**Expected shape:**

```ts
history?: { at: string; event: string }[]
```

Also consider: `evidence_hash`, `candidates`, `comment`, `updated_at` if exposed by API.

### 4. Per-run flagged records (if case detail needs run context)

Runs store aggregate counts only (`auto_matched`, `ai_resolved`, …). If UI needs “which records flagged in this run” without recomputing, backend would need to persist `flagged_records[]` on each run (Streamlit app did this historically).

### 5. Transactions recompute accuracy

`GET /api/transactions` re-runs engine over all batches together. May differ from per-batch sync results. If UI shows discrepancies, backend should either reconcile per-batch or persist transaction ledger at sync time.

### 6. SSE / streaming for sync steps (nice-to-have)

`POST /api/sync-and-reconcile` returns all steps after completion. Live step animation would need SSE or WebSocket — not required for v1; frontend can animate completed steps from response.

---

## Build status summary

| Area | Status |
|------|--------|
| Login | ✅ Built |
| Dashboard | ✅ Built (v1) — includes new header + date nav |
| Reconciliations | ✅ Built (v1) |
| Settings | ✅ Built (v1) |
| Shell (sidebar, header, bell, theme, logo) | ✅ Built |
| Cases list | 🔲 Stub (URL filters + count only) — **build next** |
| Case detail | 🔲 Stub (back link + case id) |
| Transactions | 🔲 Stub |

**Recommended build order:** Cases → Case detail → Transactions. Reconciliations UX may be refined per feedback.

---

## Open questions / assumptions

1. **`run_date` wiring** — Should `selectedDate` on dashboard filter by run timestamp only, or also affect case visibility? Currently cases are **not** date-filtered; only runs are.

2. **AI contribution metric** — Dashboard uses run-level `ai_resolved / total_records`. Confirm this matches product language vs case-level “Gemini investigated” counts.

3. **Dev proxy port** — `vite.config.ts` currently proxies to **8001** (local uvicorn default in this repo). Change target if API runs on another port. Production should use `VITE_API_URL` pointing at deployed API.

4. **`dismissNotification`** — Removed from AppContext; closing bell popover is local UI state only. Server `notification_seen` is returned but not updated from frontend yet.

5. **Case detail AI chat** — `POST /api/ask-ai` is read-only; full assistant UI scope TBD (case-scoped vs global).

6. **Dashboard date nav** — Cannot select or step past today. Previous day has no lower bound.

7. **Responsive breakpoints** — Dashboard charts scroll horizontally on narrow viewports; tables on Cases/Transactions should use contained scroll per hard rules.

---

## Hard rules (checklist for every PR)

1. Never invent data — if an endpoint doesn't provide it, show empty / “Not enough data yet”.
2. Never merge `ai_pending` and `manual_review` in UI.
3. Money in paise; display via `formatINR` only.
4. Confidence null → “Pending” or “—”, never fake percentages.
5. Disabled buttons must look disabled.
6. No horizontal page scroll; wide tables scroll inside their container.

---

*Last updated: Aug 29, 2026 — Reconciliations v1, dashboard header (welcome row + ← date →), AppContext batch/run fields. Next: Cases list.*
