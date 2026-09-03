import {
  transactionStatusBadgeClass,
  transactionStatusLabel,
  transactionUiStatus,
} from '../../lib/transactionDisplay'
import { formatINR } from '../../lib/money'
import type { TransactionRecord } from '../../lib/api'
import type { Case } from '../../types/case'

type TransactionsTableProps = {
  records: TransactionRecord[]
  selectedId: string | null
  onSelect: (record: TransactionRecord) => void
  emptyMessage: string
  casesById: Map<string, Case>
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.5">
      <path d="M2.5 10s2.5-5 7.5-5 7.5 5 7.5 5-2.5 5-7.5 5-7.5-5-7.5-5z" />
      <circle cx="10" cy="10" r="2.25" />
    </svg>
  )
}

export function TransactionsTable({
  records,
  selectedId,
  onSelect,
  emptyMessage,
  casesById,
}: TransactionsTableProps) {
  if (records.length === 0) {
    return (
      <p className="px-5 py-14 text-center text-[13px] text-zinc-400 dark:text-zinc-500">
        {emptyMessage}
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[880px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-zinc-100 text-[11px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
            <th className="px-5 py-3">Record ID</th>
            <th className="px-5 py-3">Tier</th>
            <th className="px-5 py-3">Expected</th>
            <th className="px-5 py-3">Received</th>
            <th className="px-5 py-3">Delta</th>
            <th className="px-5 py-3">Status</th>
            <th className="px-5 py-3 text-right">Details</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {records.map((record) => {
            const uiStatus = transactionUiStatus(record, casesById)
            const isSelected = selectedId === record.record_id

            return (
              <tr
                key={record.record_id}
                className={`cursor-pointer text-zinc-700 transition-colors dark:text-zinc-300 ${
                  isSelected
                    ? 'bg-zinc-50 dark:bg-zinc-800/60'
                    : 'hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40'
                }`}
                onClick={() => onSelect(record)}
              >
                <td className="px-5 py-3.5 font-medium text-zinc-900 dark:text-zinc-50">
                  {record.record_id}
                </td>
                <td className="px-5 py-3.5 text-zinc-500">
                  {/* Settlement-feed rows have no tier -- show the name
                      alone rather than a dangling "· Settlement feed". */}
                  {record.tier === null ? record.tier_name : `${record.tier} · ${record.tier_name}`}
                </td>
                <td className="px-5 py-3.5 tabular-nums">{formatINR(record.expected)}</td>
                <td className="px-5 py-3.5 tabular-nums">{formatINR(record.received)}</td>
                <td className="px-5 py-3.5 tabular-nums">
                  {record.delta === 0 ? (
                    <span className="text-zinc-400">—</span>
                  ) : (
                    formatINR(record.delta)
                  )}
                </td>
                <td className="px-5 py-3.5">
                  <span
                    className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${transactionStatusBadgeClass(uiStatus)}`}
                  >
                    {transactionStatusLabel(uiStatus)}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-right">
                  <button
                    type="button"
                    aria-label={`View ${record.record_id}`}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-700 dark:hover:text-zinc-100"
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelect(record)
                    }}
                  >
                    <EyeIcon />
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
