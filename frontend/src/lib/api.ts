/**
 * Typed client for the Ledgr API (../../api.py).
 *
 * This is the ONLY place the frontend talks to the backend. Every number
 * rendered anywhere in this app originates from one of these calls — nothing
 * downstream computes a financial figure of its own.
 *
 * Money crosses this boundary as INTEGER PAISE, exactly as the reconciliation
 * engine produced it. Format with money.ts at render time; never convert here,
 * or rounding gets two sources of truth.
 */
import type { Case, MerchantSession, ReconciliationRun } from '../types/case'

const BASE = import.meta.env.VITE_API_URL ?? ''
const TOKEN_KEY = 'ledgr_token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable (private mode) — session simply won't persist */
  }
}

/** Thrown for any non-2xx response. `status` lets callers distinguish the
 *  cases that genuinely mean different things — notably 429 (AI rate limit,
 *  retryable) from 503 (AI down) from 400 (validation, e.g. a manual review
 *  submitted without the required comment). */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    })
  } catch {
    // Network-level failure: the API isn't running, or CORS blocked it.
    // Say so plainly rather than surfacing a bare "Failed to fetch".
    throw new ApiError(0, 'Cannot reach the Ledgr API. Is it running on port 8000?')
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* non-JSON error body — keep statusText */
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// ---------------------------------------------------------------------------
// Response shapes
// ---------------------------------------------------------------------------
export type AppState = {
  current_batch: number
  total_batches: number
  batch_available: boolean
  next_batch_available_at: string | null
  notification_seen: boolean
  notification_batch: number | null
  reconciliation_runs: ReconciliationRun[]
  cases: Record<string, Case>
  /** All COD ageing is measured against this date, not the wall clock, so
   *  runs stay reproducible. Age cases against THIS or the frontend's buckets
   *  will silently disagree with the engine's own thresholds. */
  run_date: string
}

export type SourceStatus = {
  name: string
  status: string
  message: string
  count: number
}

export type Sources = {
  orders: SourceStatus
  settlements: SourceStatus
  bank: SourceStatus
}

export type Settings = {
  fee_tolerance_pct: number
  fee_tolerance_abs_paise: number
  cod_tolerance_pct: number
  cod_tolerance_abs_paise: number
  cod_fresh_days: number
  cod_warn_days: number
  run_date: string
  ai_model: string
  ai_batch_size: number
  auto_resolve_confidence_floor: number
  total_batches: number
}

export type SyncStep = { label: string; result: string }

export type SyncResult = {
  run: ReconciliationRun
  steps: SyncStep[]
  cases: Record<string, Case>
}

export type TransactionRecord = {
  record_id: string
  order_date: string
  payment_mode: string
  tier: number
  tier_name: string
  status: string
  reason: string
  reason_label: string
  expected: number
  received: number
  delta: number
  amount_at_risk: number
  priority: string
  explanation: string
  matched_settlement: string
  age_days: number | null
  ai_assisted: boolean
  case_id: string | null
}

export type CaseEvidence = {
  order: {
    order_id: string
    order_date: string
    customer_name: string
    customer_phone: string
    customer_email: string
    courier: string
    payment_mode: string
    gateway_ref_id: string
    bank_utr: string
    amount: number
    source: string
  } | null
  settlement: {
    settlement_id: string
    settled_on: string
    amount_received: number
    gateway_ref_id: string
    bank_utr: string
    source: string
    narration: string
  } | null
  /** The real Tier-2 tolerance band the engine applied to THIS order. */
  fee_structure: {
    payment_mode: string
    tolerance_pct: number
    tolerance_flat: number
    order_amount: number
    max_explainable_shortfall: number
    /** False when nothing was received yet — a fee comparison is meaningless
     *  until money actually arrives, so shortfall/within_band are null. */
    comparable: boolean
    actual_shortfall: number | null
    within_band: boolean | null
  } | null
  history: { at: string; event: string }[]
}

export type MessageOption = {
  recipient_type: 'gateway' | 'courier' | 'customer'
  label: string
  /** Empty when we genuinely hold no address — show the note, never invent one. */
  address: string
  note: string
  why: string
}

export type MessageDraft = {
  subject: string
  body: string
  /** The concrete case facts the draft cites — lets a human audit it fast. */
  facts_used: string[]
  recipient_type: string
  provider: string | null
}

export type AskResult = {
  answer: string
  /** 'python' = answered from persisted data at zero API cost;
   *  'gemini' = a real model call was made. Surface this honestly. */
  source: string
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------
export const api = {
  async login(email: string, password: string) {
    const res = await request<{ token: string; merchant: MerchantSession }>(
      '/api/login',
      { method: 'POST', body: JSON.stringify({ email, password }) },
    )
    setToken(res.token)
    return res.merchant
  },

  async logout() {
    try {
      await request('/api/logout', { method: 'POST' })
    } finally {
      setToken(null)
    }
  },

  me: () => request<{ merchant: MerchantSession }>('/api/me'),

  getState: () => request<AppState>('/api/state'),
  getSources: () => request<Sources>('/api/sources'),
  getSettings: () => request<Settings>('/api/settings'),
  reset: () => request<{ ok: boolean }>('/api/reset', { method: 'POST' }),

  syncAndReconcile: () =>
    request<SyncResult>('/api/sync-and-reconcile', { method: 'POST' }),

  getTransactions: () =>
    request<{ records: TransactionRecord[]; total: number }>('/api/transactions'),

  getCases: (params?: { case_status?: string; case_type?: string }) => {
    const q = new URLSearchParams(
      Object.entries(params ?? {}).filter(([, v]) => Boolean(v)) as [string, string][],
    ).toString()
    return request<{ cases: Case[] }>(`/api/cases${q ? `?${q}` : ''}`)
  },

  getCase: (caseId: string) => request<Case>(`/api/cases/${caseId}`),

  /** Real order / settlement / fee-band records behind a case. Any section
   *  with no underlying record comes back null — hide it, don't fake it. */
  getCaseEvidence: (caseId: string) =>
    request<CaseEvidence>(`/api/cases/${caseId}/evidence`),

  /** Who it makes sense to contact about this case, from its own facts. */
  getMessageOptions: (caseId: string) =>
    request<{ options: MessageOption[] }>(`/api/cases/${caseId}/message-options`),

  /** Drafts only — Ledgr never sends. The human edits and sends it themselves. */
  draftMessage: (caseId: string, recipientType: string) =>
    request<MessageDraft>(`/api/cases/${caseId}/draft-message`, {
      method: 'POST',
      body: JSON.stringify({ recipient_type: recipientType }),
    }),

  /** `comment` is REQUIRED by the server for manual_review and a 400 comes
   *  back without one — that rule is enforced backend-side on purpose, since
   *  the reviewer's justification is the audit trail. */
  resolveCase: (caseId: string, resolutionType: 'accepted' | 'manual_review',
                comment?: string) =>
    request<Case>(`/api/cases/${caseId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution_type: resolutionType, comment }),
    }),

  reopenCase: (caseId: string, reason: string) =>
    request<Case>(`/api/cases/${caseId}/reopen`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  toggleBookmark: (caseId: string) =>
    request<{ case_id: string; bookmarked: boolean }>(
      `/api/cases/${caseId}/bookmark`, { method: 'POST' },
    ),

  setComment: (caseId: string, comment: string) =>
    request<Case>(`/api/cases/${caseId}/comment`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }),

  retryAi: (caseId: string) =>
    request<Case>(`/api/cases/${caseId}/retry-ai`, { method: 'POST' }),

  /** The one controlled agentic step — spends real AI quota. User-triggered
   *  only; never call this automatically or on mount. */
  investigateFurther: (caseId: string) =>
    request<Case>(`/api/cases/${caseId}/investigate-further`, { method: 'POST' }),

  /** `history` lets follow-up questions resolve references ("his name?",
   *  "that order"). Facts still come only from the reconciliation data. */
  askAi: (question: string, caseId?: string,
          history: { question: string; answer: string }[] = []) =>
    request<AskResult>('/api/ask-ai', {
      method: 'POST',
      body: JSON.stringify({ question, case_id: caseId ?? null, history }),
    }),
}
