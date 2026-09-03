import type { TransactionRecord } from './api'
import { COD_WARN_DAYS } from './constants'
import type { Case } from '../types/case'
import { aiReachedVerdict, isOpenForReview } from './caseUtils'

export type TransactionUiStatus =
  | 'matched'
  | 'resolved'
  | 'ai_recommendation'
  | 'needs_investigation'
  | 'awaiting_settlement'
  | 'exception'

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

/**
 * `record` is engine.py's raw, stateless per-run tier output -- it re-scores
 * the same way every time and has no idea a case built on top of it was
 * later resolved (by a human, or by the remittance join proving a bulk-COD
 * credit was already paid). Without `casesById`, a resolved bulk order kept
 * reading "EXCEPTION -- Matched settlement: Not linked" here while its own
 * case page said "Resolved automatically" -- the same money, two
 * contradictory screens. The case, when one exists, is the source of truth
 * for anything the engine's own tier can't have known about after the fact.
 */
export function transactionUiStatus(
  record: TransactionRecord,
  casesById?: Map<string, Case>,
): TransactionUiStatus {
  const linkedCase = record.case_id ? casesById?.get(record.case_id) : undefined

  if (linkedCase?.resolution?.resolved) {
    return 'resolved'
  }

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

  // Once a case exists, its own AI verdict is the real split -- the same
  // "AI recommendation" vs "needs investigation" line already drawn on
  // Cases/Reconciliations. The engine's structural ai_assisted flag is only
  // a fallback for the rare record whose case object hasn't loaded yet.
  if (linkedCase) {
    return aiReachedVerdict(linkedCase) ? 'ai_recommendation' : 'needs_investigation'
  }
  if (record.ai_assisted || record.status === 'MANUAL_REVIEW') {
    return 'needs_investigation'
  }
  return 'exception'
}

export function transactionStatusLabel(status: TransactionUiStatus): string {
  switch (status) {
    case 'matched':
      return 'Matched'
    case 'resolved':
      return 'Resolved'
    case 'ai_recommendation':
      return 'AI recommendation'
    case 'needs_investigation':
      return 'Needs investigation'
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
    case 'resolved':
      return 'bg-teal-50 text-teal-700 dark:bg-teal-500/15 dark:text-teal-300'
    case 'ai_recommendation':
      return 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'
    case 'needs_investigation':
      return 'bg-orange-50 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300'
    case 'awaiting_settlement':
      return 'bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200'
    case 'exception':
      return 'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300'
  }
}

/**
 * A record's own reason/explanation/settlement fields are frozen from
 * engine.py's original pass. Once the linked case is resolved, its fields
 * are the ones actually kept current (remittance apply, human resolution) --
 * prefer them so the drawer stops repeating a stale "Not linked" next to a
 * case that says it was paid.
 */
export function transactionDisplayFields(
  record: TransactionRecord,
  linkedCase?: Case,
): {
  reasonLabel: string
  explanation: string
  matchedSettlement: string | null
  amountAtRisk: number
} {
  if (linkedCase?.resolution?.resolved) {
    return {
      reasonLabel: linkedCase.reason_label || record.reason_label,
      explanation: linkedCase.explanation || record.explanation,
      matchedSettlement: linkedCase.settlement_id || record.matched_settlement,
      // The case's own amount_at_risk is what remittance apply / resolution
      // actually zeroed out. record.amount_at_risk is frozen from before
      // that -- showing it here would say "resolved" and "₹999 at risk" in
      // the same panel.
      amountAtRisk: linkedCase.amount_at_risk,
    }
  }
  return {
    reasonLabel: record.reason_label,
    explanation: record.explanation,
    matchedSettlement: record.matched_settlement,
    amountAtRisk: record.amount_at_risk,
  }
}

export function canViewCaseForTransaction(
  record: TransactionRecord,
  casesById: Map<string, Case>,
): boolean {
  if (!record.case_id) return false
  const caseItem = casesById.get(record.case_id)
  if (!caseItem) return false
  // A COD order still inside its collection window has a case object but
  // nothing worth clicking into yet -- that's the "awaiting settlement"
  // informational branch in the drawer. Anything else with a case, open OR
  // already resolved, is real: resolved used to be excluded here (isOpenForReview
  // is false once resolved), which hid the "View case" link -- and the whole
  // remittance breakdown behind it -- for every auto-resolved bulk-COD order.
  return isOpenForReview(caseItem) || Boolean(caseItem.resolution?.resolved)
}

export function filterTransactions(
  records: TransactionRecord[],
  filters: TransactionFilters,
  casesById?: Map<string, Case>,
): TransactionRecord[] {
  const query = filters.search.trim().toLowerCase()

  return records.filter((record) => {
    const uiStatus = transactionUiStatus(record, casesById)
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
