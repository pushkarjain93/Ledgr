import { useState } from 'react'
import { caseDisplayId, formatCaseDate } from '../../lib/caseDisplay'
import { caseAgeDays, formatAge, orderOrCustomerLabel } from '../../lib/caseUtils'
import { COD_WARN_DAYS } from '../../lib/constants'
import { formatINR } from '../../lib/money'
import type { Case } from '../../types/case'

function codAgeBadge(caseItem: Case): { label: string; className: string } {
  const days = caseAgeDays(caseItem)
  if (days > COD_WARN_DAYS) {
    return {
      label: 'Overdue',
      className: 'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300',
    }
  }
  if (days > 7) {
    return {
      label: 'Approaching',
      className: 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
    }
  }
  return {
    label: 'On track',
    className: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  }
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      className={`h-4 w-4 shrink-0 text-zinc-400 transition-transform ${open ? 'rotate-180' : ''}`}
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden
    >
      <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

type CodAwaitingSettlementPanelProps = {
  cases: Case[]
}

export function CodAwaitingSettlementPanel({ cases }: CodAwaitingSettlementPanelProps) {
  const [open, setOpen] = useState(false)
  const totalExpected = cases.reduce((sum, c) => sum + c.expected, 0)

  return (
    <div className="rounded-xl border border-zinc-200/80 bg-white shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start justify-between gap-3 px-5 py-4 text-left transition-colors hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">
              COD awaiting settlement
            </h2>
            <span className="rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-200">
              {cases.length} {cases.length === 1 ? 'order' : 'orders'}
            </span>
          </div>
          <p className="mt-1 text-[12.5px] text-zinc-500 dark:text-zinc-400">
            {cases.length === 0
              ? `No COD orders inside the ${COD_WARN_DAYS}-day collection window`
              : `${formatINR(totalExpected)} expected · informational only, not in case review`}
          </p>
        </div>
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div className="border-t border-zinc-100 dark:border-zinc-800">
          {cases.length === 0 ? (
            <p className="px-5 py-8 text-center text-[13px] text-zinc-400 dark:text-zinc-500">
              Sync and reconcile to see COD orders in the collection window.
            </p>
          ) : (
            <>
              <div className="border-b border-zinc-100 px-5 py-3 dark:border-zinc-800">
                <p className="text-[12.5px] text-zinc-600 dark:text-zinc-400">
                  Within {COD_WARN_DAYS} days of order — drops from here once overdue and moves to case review
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-[13px]">
                  <thead>
                    <tr className="border-b border-zinc-100 text-[11px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
                      <th className="px-5 py-3">Order</th>
                      <th className="px-5 py-3">Customer</th>
                      <th className="px-5 py-3">Expected</th>
                      <th className="px-5 py-3">Order date</th>
                      <th className="px-5 py-3">Age</th>
                      <th className="px-5 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                    {cases.map((c) => {
                      const ageBadge = codAgeBadge(c)
                      return (
                        <tr key={c.case_id} className="text-zinc-700 dark:text-zinc-300">
                          <td className="px-5 py-3.5 font-medium text-zinc-900 dark:text-zinc-50">
                            {caseDisplayId(c)}
                          </td>
                          <td className="px-5 py-3.5">{orderOrCustomerLabel(c)}</td>
                          <td className="px-5 py-3.5 tabular-nums">{formatINR(c.expected)}</td>
                          <td className="px-5 py-3.5 whitespace-nowrap text-zinc-500">
                            {formatCaseDate(c.order_date)}
                          </td>
                          <td className="px-5 py-3.5">
                            <span className="tabular-nums">{formatAge(c)}</span>
                          </td>
                          <td className="px-5 py-3.5">
                            <span
                              className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${ageBadge.className}`}
                            >
                              {ageBadge.label}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
