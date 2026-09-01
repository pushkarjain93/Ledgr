export type CaseType =
  | 'partial_payment'
  | 'overpayment'
  | 'ambiguous_match'
  | 'unmatched_settlement'
  | 'unmatched_order'
  | 'remittance_overdue'
  /** Courier remittance detail contradicts our records - see remittance.py. */
  | 'remittance_discrepancy'
  | 'pending_settlement'
  | 'settlement_matched'
  | 'exception'

export type CaseStatus =
  | 'pending_settlement'
  | 'needs_ai'
  | 'ai_pending'
  | 'ai_recommendation'
  | 'manual_review'
  | 'exception'
  | 'resolved'

export type CaseAiBlock = {
  classification?: string | null
  recommendation?: string | null
  confidence: number | null
  reason: string | null
  next_step: string | null
  evidence?: string[]
  missing_evidence?: string[]
  /** Set only after a follow-up investigation, so the UI can show a real
   *  before/after delta rather than a fabricated trend. */
  previous_confidence?: number | null
  /** Which provider produced this verdict — models calibrate differently. */
  provider?: string | null
  /**
   * Present only after "Investigate further" has run. Records what the extra
   * step actually checked and whether the verdict moved, so a re-confirmed
   * finding still visibly reports work done instead of looking like a no-op.
   */
  followup?: {
    at: string
    evidence_checked: string[]
    /** List from the backend; older records may hold a single string. */
    still_unavailable: string[] | string
    changed: boolean
    previous: { action: string | null; reasoning: string | null; next_step: string | null }
  } | null
  candidate_rankings?: Array<{ id: string; confidence: number; reason: string }>
  action: 'resolve' | 'manual_review' | 'escalate' | null
  investigated_at?: string | null
  error: string | null
}

export type CaseHistoryEvent = {
  at: string
  event: string
}

export type Case = {
  case_id: string
  record_id: string
  order_id: string | null
  settlement_id: string | null
  customer_name: string
  order_date: string
  /** From the order feed; blank for settlement-only cases. */
  payment_mode?: string
  batch_id: string | number
  case_type: CaseType
  /** Set when this order was paid inside a bulk courier remittance. */
  remittance?: {
    utr: string; settlement_id: string; awb: string; courier: string
    remitted_on: string; cod_collected: number; cod_fee: number
    freight_fee: number; net_payout: number
    batch_order_count: number; batch_credit: number
  } | null
  /** Set on the bank credit itself: the batch it turned out to be. */
  remittance_batch?: {
    utr: string; courier: string; remitted_on: string; order_count: number
    rows_total: number; credit_amount: number; order_ids: string[]
  } | null
  /** Discrepancies the remittance join could not square for this record. */
  remittance_findings?: { kind: string; detail: string; amount_at_risk: number }[]
  case_status: CaseStatus
  expected: number
  received: number
  delta: number
  amount_at_risk: number
  reason_label: string
  explanation: string
  priority: string
  bookmarked: boolean
  comment?: string
  updated_at?: string
  ai: CaseAiBlock | null
  resolution: {
    resolved: boolean
    resolution_type: 'accepted' | 'manual_review' | 'auto_resolved' | null
    resolved_at: string | null
    resolved_by?: string | null
    comment: string | null
  }
  history?: CaseHistoryEvent[]
  created_at: string
}

export type ReconciliationRun = {
  run_id: string
  batch_id: number
  timestamp: string
  sources: string
  status: string
  auto_matched?: number
  /** COD inside its collection window: not matched, not a failure. */
  awaiting_settlement?: number
  ai_resolved?: number
  exceptions?: number
  total_records?: number
  expected_paise?: number
  received_paise?: number
}

export type MerchantState = {
  current_batch: number
  processed_record_ids: string[]
  reconciliation_runs: ReconciliationRun[]
  next_batch_available_at: string | null
  notification_batch: number | null
  notification_created: boolean
  notification_seen: boolean
  cases: Record<string, Case>
  /** Cumulative, de-duplicated order records reconciled across all batches. */
  orders_processed: number
}

export type MerchantSession = {
  email: string
  company_name: string
  merchant_id: string
}
