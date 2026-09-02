import { Link } from 'react-router-dom'
import { formatINR } from '../../lib/money'
import { issueTypeLabel, hasWorkingNote } from '../../lib/caseUtils'
import { caseDetailPath } from '../../lib/caseQueue'
import {
  caseDisplayId,
} from '../../lib/caseDisplay'
import type { Case } from '../../types/case'

type CasesTableProps = {
  cases: Case[]
  filter?: string | null
  emptyMessage?: string
}

export function CasesTable({ cases, filter = null, emptyMessage = 'No cases match this filter.' }: CasesTableProps) {
  if (cases.length === 0) {
    return (
      <p className="px-5 py-14 text-center text-[13px] text-zinc-400 dark:text-zinc-500">
        {emptyMessage}
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[960px] text-left text-[13px]">
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
          {cases.map((c) => {
            const id = caseDisplayId(c)

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
                    <div>
                      <span className="font-medium text-zinc-900 dark:text-zinc-50">
                        {id}
                        {c.bookmarked && (
                          <span className="ml-1.5 text-amber-500" title="Bookmarked" aria-label="Bookmarked">
                            ★
                          </span>
                        )}
                      </span>
                      {c.customer_name?.trim() && (
                        <p className="text-[11px] text-zinc-400">{c.customer_name}</p>
                      )}
                    </div>
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
                  {/* A note means a human already looked and left something
                      behind. Surfacing it here is what makes the "My notes"
                      filter findable without opening every case. */}
                  {hasWorkingNote(c) && (
                    <span
                      title={c.comment ?? undefined}
                      className="ml-2 rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
                    >
                      Note
                    </span>
                  )}
                </td>
                <td className="px-5 py-3.5">
                  <Link
                    to={caseDetailPath(c.case_id, filter)}
                    className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                  >
                    {c.resolution?.resolved ? 'View case →' : 'Review case →'}
                  </Link>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
