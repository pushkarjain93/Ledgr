export type CaseType =
  | 'partial_payment'
  | 'overpayment'
  | 'ambiguous_match'
  | 'unmatched_settlement'
  | 'unmatched_order'
  | 'remittance_overdue'
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
}

export type MerchantSession = {
  email: string
  company_name: string
  merchant_id: string
}
