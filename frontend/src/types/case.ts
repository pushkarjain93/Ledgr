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

export type Case = {
  case_id: string
  record_id: string
  order_id: string | null
  settlement_id: string | null
  customer_name: string
  order_date: string
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
  ai: {
    confidence: number | null
    reason: string | null
    next_step: string | null
    action: 'resolve' | 'manual_review' | 'escalate' | null
    error: string | null
  } | null
  resolution: {
    resolved: boolean
    resolution_type: 'accepted' | 'manual_review' | 'auto_resolved' | null
    resolved_at: string | null
    comment: string | null
  }
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
