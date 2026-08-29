import { COD_WARN_DAYS, ISSUE_TYPE_LABELS, RUN_DATE } from './constants'
import type { Case, CaseStatus, CaseType } from '../types/case'

export function isUnresolved(caseItem: Case): boolean {
  return !caseItem.resolution?.resolved
}

/** COD still inside the 0–14 day collection window (informational only). */
export function isWithinCodSettlementWindow(
  caseItem: Case,
  referenceDate = RUN_DATE,
): boolean {
  return caseAgeDays(caseItem, referenceDate) <= COD_WARN_DAYS
}

export function isAwaitingSettlementCase(
  caseItem: Case,
  referenceDate = RUN_DATE,
): boolean {
  return (
    isUnresolved(caseItem) &&
    caseItem.case_status === 'pending_settlement' &&
    isWithinCodSettlementWindow(caseItem, referenceDate)
  )
}

/** Open cases that actually need human or AI review — excludes in-window COD waits. */
export function isOpenForReview(caseItem: Case, referenceDate = RUN_DATE): boolean {
  if (!isUnresolved(caseItem)) return false
  if (
    caseItem.case_status === 'pending_settlement' &&
    isWithinCodSettlementWindow(caseItem, referenceDate)
  ) {
    return false
  }
  return true
}

export function caseAgeDays(caseItem: Case, referenceDate = RUN_DATE): number {
  const ref = parseISODate(referenceDate)
  if (caseItem.order_id && caseItem.order_date) {
    return daysBetween(parseISODate(caseItem.order_date), ref)
  }
  return daysBetween(parseISODate(caseItem.created_at.slice(0, 10)), ref)
}

export function formatAge(caseItem: Case): string {
  const days = caseAgeDays(caseItem)
  if (days === 0) return 'Today'
  if (days === 1) return '1 day'
  return `${days} days`
}

export function issueTypeLabel(caseType: CaseType | string): string {
  return ISSUE_TYPE_LABELS[caseType] ?? caseType.replace(/_/g, ' ')
}

export function displayConfidence(caseItem: Case): string {
  const confidence = caseItem.ai?.confidence
  if (confidence === null || confidence === undefined) {
    if (caseItem.case_status === 'ai_pending') return 'Pending'
    return '—'
  }
  return `${confidence}%`
}

export function orderOrCustomerLabel(caseItem: Case): string {
  if (caseItem.customer_name?.trim()) {
    return caseItem.customer_name
  }
  if (caseItem.order_id) return caseItem.order_id
  if (caseItem.settlement_id) return caseItem.settlement_id
  return caseItem.record_id
}

export function needsHumanDecision(caseItem: Case): boolean {
  return (
    isOpenForReview(caseItem) &&
    (caseItem.case_status === 'manual_review' ||
      caseItem.case_status === 'ai_recommendation')
  )
}

export function canReopenCase(caseItem: Case): boolean {
  return (
    Boolean(caseItem.resolution?.resolved) &&
    caseItem.resolution?.resolution_type !== 'auto_resolved'
  )
}

export const HUMAN_DECISION_STATUSES: CaseStatus[] = [
  'manual_review',
  'ai_recommendation',
]

function parseISODate(value: string): Date {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function daysBetween(start: Date, end: Date): number {
  const ms = end.getTime() - start.getTime()
  return Math.max(0, Math.floor(ms / 86400000))
}
