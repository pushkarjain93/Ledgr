import { Link } from 'react-router-dom'
import { formatINR } from '../../lib/money'
import { caseDetailPath } from '../../lib/caseQueue'
import { scrollAppMainToTop } from '../../lib/scrollAppMain'
import type { Case, CaseStatus } from '../../types/case'
import { isOpenForReview } from '../../lib/caseUtils'

function confidenceTier(confidence: number | null | undefined): {
  label: 'High' | 'Medium' | 'Low' | 'Pending'
  badgeClass: string
} {
  if (confidence === null || confidence === undefined) {
    return {
      label: 'Pending',
      badgeClass: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300',
    }
  }
  if (confidence >= 80) {
    return {
      label: 'High',
      badgeClass: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
    }
  }
  if (confidence >= 50) {
    return {
      label: 'Medium',
      badgeClass: 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
    }
  }
  return {
    label: 'Low',
    badgeClass: 'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  }
}

function statusBadge(status: CaseStatus): string {
  switch (status) {
    case 'ai_recommendation':
    case 'ai_pending':
    case 'manual_review':
      return 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'
    case 'exception':
      return 'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300'
    default:
      return 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300'
  }
}

function statusLabel(status: CaseStatus): string {
  switch (status) {
    case 'ai_recommendation':
    case 'ai_pending':
    case 'manual_review':
      return 'AI Review'
    case 'exception':
      return 'Exception'
    default:
      return status.replace(/_/g, ' ')
  }
}

function reviewCases(cases: Case[]): Case[] {
  return cases
    .filter(
      (c) =>
        isOpenForReview(c) &&
        c.case_status !== 'pending_settlement' &&
        c.case_status !== 'needs_ai',
    )
    .sort((a, b) => b.amount_at_risk - a.amount_at_risk)
}

type AiReviewQueueProps = {
  cases: Case[]
  reviewCount: number
}

export function AiReviewQueue({ cases, reviewCount }: AiReviewQueueProps) {
  const queue = reviewCases(cases).slice(0, 8)

  return (
    <div className="rounded-xl border border-zinc-200/80 bg-white shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">AI Review Queue</h2>
          <span className="rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-500/15 dark:text-blue-300">
            {reviewCount} cases require review
          </span>
        </div>
        <Link
          to="/cases"
          onClick={scrollAppMainToTop}
          className="text-[12px] font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          View all cases →
        </Link>
      </div>

      {queue.length === 0 ? (
        <p className="px-5 py-10 text-center text-[13px] text-zinc-400">No cases in the review queue yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-zinc-100 text-[11px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
                <th className="px-5 py-3">Order ID</th>
                <th className="px-5 py-3">Expected</th>
                <th className="px-5 py-3">Received</th>
                <th className="px-5 py-3">AI Confidence</th>
                <th className="px-5 py-3">AI Recommendation</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {queue.map((c) => {
                const conf = c.ai?.confidence
                const tier = confidenceTier(conf)
                const id = c.order_id ?? c.record_id
                const recommendation =
                  c.ai?.reason?.trim() || c.reason_label || c.explanation || '—'

                return (
                  <tr key={c.case_id} className="text-zinc-700 dark:text-zinc-300">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400">
                          <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5" stroke="currentColor" strokeWidth="1.5">
                            <path d="M4 3h8v10H4z" />
                            <path d="M6 6h4M6 8.5h4" strokeLinecap="round" />
                          </svg>
                        </span>
                        <span className="font-medium text-zinc-900 dark:text-zinc-50">{id}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 tabular-nums">{formatINR(c.expected)}</td>
                    <td className="px-5 py-3.5 tabular-nums">{formatINR(c.received)}</td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold ${tier.badgeClass}`}
                      >
                        {conf !== null && conf !== undefined ? `${conf}%` : '—'} {tier.label}
                      </span>
                    </td>
                    <td className="max-w-[200px] truncate px-5 py-3.5 text-zinc-600 dark:text-zinc-400">
                      {recommendation}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${statusBadge(c.case_status)}`}
                      >
                        {statusLabel(c.case_status)}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <Link
                        to={caseDetailPath(c.case_id, null)}
                        className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                      >
                        Review Case →
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
