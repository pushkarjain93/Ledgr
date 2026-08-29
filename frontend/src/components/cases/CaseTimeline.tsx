import { formatCaseTimestamp } from '../../lib/caseDisplay'
import type { Case, CaseHistoryEvent } from '../../types/case'

type CaseTimelineProps = {
  history: CaseHistoryEvent[]
}

export function CaseTimeline({ history }: CaseTimelineProps) {
  const events = [...history].sort((a, b) => b.at.localeCompare(a.at))

  if (events.length === 0) {
    return (
      <p className="text-[13px] text-zinc-400">No activity recorded yet.</p>
    )
  }

  return (
    <ol className="space-y-4">
      {events.map((entry, index) => (
        <li key={`${entry.at}-${index}`} className="flex gap-4">
          <div className="w-[140px] shrink-0 text-[12px] tabular-nums text-zinc-400">
            {formatCaseTimestamp(entry.at)}
          </div>
          <div className="relative flex-1 pb-1 pl-4">
            <span className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-zinc-300 dark:bg-zinc-600" />
            <p className="text-[13px] text-zinc-700 dark:text-zinc-300">{entry.event}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

type CaseResolvedBannerProps = {
  caseItem: Case
  onReopen?: () => void
  canReopen?: boolean
}

export function CaseResolvedBanner({ caseItem, onReopen, canReopen = false }: CaseResolvedBannerProps) {
  const resolution = caseItem.resolution
  if (!resolution?.resolved) return null

  const isAutoResolved = resolution.resolution_type === 'auto_resolved'
  const typeLabel =
    resolution.resolution_type === 'accepted'
      ? 'AI Recommendation Accepted'
      : resolution.resolution_type === 'manual_review'
        ? 'Kept for Manual Review'
        : resolution.resolution_type === 'auto_resolved'
          ? 'Closed automatically'
          : resolution.resolution_type ?? 'Resolved'

  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 dark:border-emerald-500/30 dark:bg-emerald-950/30">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <p className="text-[16px] font-semibold text-emerald-800 dark:text-emerald-200">
          {isAutoResolved ? 'Case closed automatically' : 'Case resolved successfully'}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {canReopen && onReopen ? (
            <button
              type="button"
              onClick={onReopen}
              className="rounded-lg border border-emerald-300 bg-white px-3 py-1.5 text-[13px] font-medium text-emerald-800 transition-colors hover:bg-emerald-100 dark:border-emerald-500/40 dark:bg-emerald-950/50 dark:text-emerald-100 dark:hover:bg-emerald-900/40"
            >
              Reopen for review
            </button>
          ) : null}
        </div>
      </div>
      {isAutoResolved ? (
        <p className="mt-2 text-[13px] leading-relaxed text-emerald-800/90 dark:text-emerald-200/90">
          Settlement arrived and this case was closed by the system.
        </p>
      ) : null}
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-emerald-600/80">Resolution type</p>
          <p className="text-[13px] font-medium text-emerald-900 dark:text-emerald-100">{typeLabel}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-emerald-600/80">Resolved by</p>
          <p className="text-[13px] font-medium text-emerald-900 dark:text-emerald-100">
            {resolution.resolved_by ?? 'User'}
          </p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-emerald-600/80">Resolved at</p>
          <p className="text-[13px] font-medium text-emerald-900 dark:text-emerald-100">
            {formatCaseTimestamp(resolution.resolved_at)}
          </p>
        </div>
      </div>
      {resolution.comment && (
        <p className="mt-3 text-[13px] leading-relaxed text-emerald-800/90 dark:text-emerald-200/90">
          {resolution.comment}
        </p>
      )}
    </div>
  )
}
