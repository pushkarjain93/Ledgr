/** Mirrors config.py — demo "as of" date, not browser clock. */
export const RUN_DATE = '2026-09-01'

export const TOTAL_BATCHES = 2

export const DEMO_MERCHANT = {
  email: 'demo@acmecorp.com',
  company_name: 'Acme Corporation',
  merchant_id: 'merchant_acme_001',
} as const

export const ISSUE_TYPE_LABELS: Record<string, string> = {
  partial_payment: 'Short-paid',
  overpayment: 'Overpaid',
  ambiguous_match: 'Ambiguous match',
  unmatched_settlement: 'Unmatched settlement',
  unmatched_order: 'Unmatched order',
  remittance_overdue: 'Remittance overdue',
  pending_settlement: 'Awaiting settlement',
  settlement_matched: 'Settlement matched',
  exception: 'Exception',
}
