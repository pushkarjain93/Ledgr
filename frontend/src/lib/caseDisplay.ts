import type { Case, CaseStatus } from '../types/case'

// No confidence-tier helper here on purpose. The model's self-reported
// confidence is not shown in the UI and gates nothing: measured on this
// project's own data it carried almost no signal (83% of cases returned
// exactly 10). Auto-resolve is gated on EXPOSURE instead -- see
// AUTO_RESOLVE_MAX_PCT / AUTO_RESOLVE_MAX_ABS in case_engine.py.

export function caseStatusBadgeClass(status: CaseStatus, resolved: boolean): string {
  if (resolved) {
    return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
  }
  switch (status) {
    case 'ai_recommendation':
      return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
    case 'ai_pending':
    case 'manual_review':
      return 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'
    case 'exception':
      return 'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300'
    case 'pending_settlement':
      return 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
    default:
      return 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300'
  }
}

export function caseStatusLabel(caseItem: Case): string {
  if (caseItem.resolution?.resolved) return 'Resolved'
  switch (caseItem.case_status) {
    case 'ai_recommendation':
      return 'AI Recommendation'
    case 'ai_pending':
      return 'AI Pending'
    case 'manual_review':
      return 'Manual Review'
    case 'exception':
      return 'Exception'
    case 'pending_settlement':
      return 'Awaiting Settlement'
    case 'needs_ai':
      return 'Needs AI'
    default:
      return caseItem.case_status.replace(/_/g, ' ')
  }
}

export function caseDisplayId(caseItem: Case): string {
  return caseItem.order_id ?? caseItem.settlement_id ?? caseItem.record_id
}

export function formatCaseTimestamp(iso: string | null | undefined): string {
  if (!iso) return '—'
  const at = new Date(iso)
  return at.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function formatCaseDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const value = iso.slice(0, 10)
  const at = new Date(value)
  if (Number.isNaN(at.getTime())) return '—'
  return at.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
