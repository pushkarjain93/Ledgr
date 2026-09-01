import { Link } from 'react-router-dom'
import { formatINR } from '../../lib/money'
import { issueTypeLabel } from '../../lib/caseUtils'
import { caseDetailPath } from '../../lib/caseQueue'
import { scrollAppMainToTop } from '../../lib/scrollAppMain'
import type { Case } from '../../types/case'
import { isOpenForReview } from '../../lib/caseUtils'

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
}

export function AiReviewQueue({ cases }: AiReviewQueueProps) {
  // The badge counts THE SAME filtered list the table renders, so the two can
  // never disagree. It previously came from the engine run totals
  // (aiResolved + exceptions), which counts cases still queued as `needs_ai`
  // -- cases the table deliberately hides because AI has not produced a
  // verdict to review yet. Mid-run that read "19 cases require review" above
  // an empty table.
  const reviewable = reviewCases(cases)
  const queue = reviewable.slice(0, 8)
  // Cases AI has not reached yet — hidden from the table (no verdict to show)
  // but worth naming, so an empty queue mid-run reads as "still working"
  // rather than "nothing to review".
  const investigating = cases.filter(
    (c) => !c.resolution?.resolved && c.case_status === 'needs_ai',
  ).length

  return (
    <div className="rounded-xl border border-zinc-200/80 bg-white shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">AI Review Queue</h2>
          <span className="rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-500/15 dark:text-blue-300">
            {reviewable.length} {reviewable.length === 1 ? 'case' : 'cases'} require review
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
        <p className="px-5 py-10 text-center text-[13px] text-zinc-400">
          {/* "No cases" is false while AI is still working through them --
              they exist, they just have no verdict to review yet. Saying so
              is the difference between "nothing found" and "still looking". */}
          {investigating > 0
            ? `AI is investigating ${investigating} case${investigating === 1 ? '' : 's'} — verdicts will appear here shortly.`
            : 'No cases in the review queue yet.'}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-zinc-100 text-[11px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
                <th className="px-5 py-3">Order ID</th>
                <th className="px-5 py-3">Expected</th>
                <th className="px-5 py-3">Received</th>
                <th className="px-5 py-3 text-right">At risk</th>
                <th className="px-5 py-3">Payment mode</th>
                <th className="px-5 py-3">Issue</th>
                <th className="px-5 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {queue.map((c) => {
                const id = c.order_id ?? c.record_id

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
                    <td className="px-5 py-3.5 text-right font-medium tabular-nums text-zinc-900 dark:text-zinc-50">
                    {formatINR(c.amount_at_risk)}
                  </td>
                    <td className="px-5 py-3.5">
                      {c.payment_mode ? (
                        <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                          {c.payment_mode}
                        </span>
                      ) : (
                        <span className="text-zinc-400">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-zinc-700 dark:text-zinc-300">{issueTypeLabel(c.case_type)}</span>
                      {c.case_status === 'ai_pending' && (
                        <span
                          title="AI has not managed to analyse this case yet"
                          className="ml-2 rounded-md bg-zinc-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                        >
                          AI pending
                        </span>
                      )}
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
