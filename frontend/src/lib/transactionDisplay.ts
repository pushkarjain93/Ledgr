import type { TransactionRecord } from './api'
import { COD_WARN_DAYS } from './constants'
import type { Case } from '../types/case'
import { isOpenForReview } from './caseUtils'

export type TransactionUiStatus = 'matched' | 'ai_review' | 'awaiting_settlement' | 'exception'

export type TransactionStatusFilter = 'all' | TransactionUiStatus

export type PaymentModeFilter = 'all' | string

export type TransactionFilters = {
  search: string
  date: string
  paymentMode: PaymentModeFilter
  status: TransactionStatusFilter
}

export function transactionUiStatus(record: TransactionRecord): TransactionUiStatus {
  if (record.status === 'AUTO_CLEARED' || record.status === 'CLEARED_WITH_FEE') {
    return 'matched'
  }
  if (
    record.status === 'AWAITING_REMITTANCE' ||
    record.status === 'APPROACHING_THRESHOLD' ||
    (record.reason === 'R1_AWAITING_REMITTANCE' &&
      record.age_days !== null &&
      record.age_days <= COD_WARN_DAYS)
  ) {
    return 'awaiting_settlement'
  }
  if (record.ai_assisted || record.status === 'MANUAL_REVIEW') {
    return 'ai_review'
  }
  return 'exception'
}

export function transactionStatusLabel(status: TransactionUiStatus): string {
  switch (status) {
    case 'matched':
      return 'Matched'
    case 'ai_review':
      return 'AI review'
    case 'awaiting_settlement':
      return 'Awaiting settlement'
    case 'exception':
      return 'Exception'
  }
}

export function transactionStatusBadgeClass(status: TransactionUiStatus): string {
  switch (status) {
    case 'matched':
      return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
    case 'ai_review':
      return 'bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300'
    case 'awaiting_settlement':
      return 'bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200'
    case 'exception':
      return 'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300'
  }
}

export function canViewCaseForTransaction(
  record: TransactionRecord,
  casesById: Map<string, Case>,
): boolean {
  if (!record.case_id) return false
  const caseItem = casesById.get(record.case_id)
  if (!caseItem) return false
  return isOpenForReview(caseItem)
}

export function filterTransactions(
  records: TransactionRecord[],
  filters: TransactionFilters,
): TransactionRecord[] {
  const query = filters.search.trim().toLowerCase()

  return records.filter((record) => {
    const uiStatus = transactionUiStatus(record)
    if (filters.status !== 'all' && uiStatus !== filters.status) return false
    if (filters.date && record.order_date !== filters.date) return false
    if (filters.paymentMode !== 'all' && record.payment_mode !== filters.paymentMode) return false

    if (!query) return true

    const haystack = [
      record.record_id,
      record.order_date,
      record.payment_mode,
      record.matched_settlement,
      record.reason_label,
      record.explanation,
      record.tier_name,
      record.status,
    ]
      .join(' ')
      .toLowerCase()

    return haystack.includes(query)
  })
}

export function uniquePaymentModes(records: TransactionRecord[]): string[] {
  return [...new Set(records.map((r) => r.payment_mode).filter(Boolean))].sort()
}

export function hasActiveTransactionFilters(filters: TransactionFilters): boolean {
  return Boolean(
    filters.search.trim() ||
      filters.date ||
      filters.paymentMode !== 'all' ||
      filters.status !== 'all',
  )
}
