import type { TransactionRecord } from './api'
import { COD_WARN_DAYS } from './constants'
import type { Case } from '../types/case'
import { isOpenForReview } from './caseUtils'

export type TransactionUiStatus = 'matched' | 'ai_review' | 'awaiting_settlement' | 'exception'

export type TransactionStatusFilter = 'all' | TransactionUiStatus

export type PaymentModeFilter = 'all' | string

/** 'all', a tier number as a string, or UNTIERED. */
export type TierFilter = 'all' | string

export type TransactionFilters = {
  search: string
  date: string
  paymentMode: PaymentModeFilter
  status: TransactionStatusFilter
  tier: TierFilter
}

export function transactionUiStatus(record: TransactionRecord): TransactionUiStatus {
  // 'MATCHED'/'UNMATCHED' come from settlement-feed rows (see api.py's
  // transactions endpoint). Without them a settlement that reconciled cleanly
  // fell through to 'exception' and was shown in red while its own detail
  // panel said "Engine status: MATCHED".
  if (
    record.status === 'AUTO_CLEARED' ||
    record.status === 'CLEARED_WITH_FEE' ||
    record.status === 'MATCHED'
  ) {
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
    if (filters.tier !== 'all' && tierFilterValue(record) !== filters.tier) return false

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

/** Filter value for settlement-feed rows, which carry no tier. */
export const UNTIERED = 'untiered'

/** Which tier bucket a record belongs to, as a filter value. */
export function tierFilterValue(record: TransactionRecord): string {
  return record.tier === null || record.tier === undefined ? UNTIERED : String(record.tier)
}

/**
 * Tier options actually present in the data, numeric tiers ascending and the
 * untiered settlement rows last. Derived rather than hardcoded: the tier list
 * is engine.py's to define, and offering a tier with no records is a dead
 * option.
 */
export function uniqueTierOptions(
  records: TransactionRecord[],
): { value: string; label: string }[] {
  const seen = new Map<string, string>()
  for (const r of records) {
    const value = tierFilterValue(r)
    if (seen.has(value)) continue
    // Settlement-feed rows have no tier, so they must not read "Tier -- ".
    seen.set(value, value === UNTIERED
      ? r.tier_name || 'Settlement feed'
      : `Tier ${r.tier} — ${r.tier_name}`)
  }
  return [...seen.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => {
      if (a.value === UNTIERED) return 1
      if (b.value === UNTIERED) return -1
      return Number(a.value) - Number(b.value)
    })
}

export function hasActiveTransactionFilters(filters: TransactionFilters): boolean {
  return Boolean(
    filters.search.trim() ||
      filters.date ||
      filters.paymentMode !== 'all' ||
      filters.status !== 'all' ||
      filters.tier !== 'all',
  )
}
