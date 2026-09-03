import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import type { TransactionRecord } from '../../lib/api'
import { caseDetailPath } from '../../lib/caseQueue'
import { formatCaseDate } from '../../lib/caseDisplay'
import { formatINR } from '../../lib/money'
import {
  canViewCaseForTransaction,
  transactionDisplayFields,
  transactionStatusBadgeClass,
  transactionStatusLabel,
  transactionUiStatus,
} from '../../lib/transactionDisplay'
import type { Case } from '../../types/case'

type TransactionDetailDrawerProps = {
  record: TransactionRecord
  casesById: Map<string, Case>
  onClose: () => void
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <span className="text-[12.5px] text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className="max-w-[58%] text-right text-[13px] font-medium text-zinc-900 dark:text-zinc-100">
        {value}
      </span>
    </div>
  )
}

export function TransactionDetailDrawer({
  record,
  casesById,
  onClose,
}: TransactionDetailDrawerProps) {
  const linkedCase = record.case_id ? casesById.get(record.case_id) : undefined
  const uiStatus = transactionUiStatus(record, casesById)
  const showCaseLink = canViewCaseForTransaction(record, casesById)
  const fields = transactionDisplayFields(record, linkedCase)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <>
      <button
        type="button"
        aria-label="Close details"
        className="fixed inset-0 z-40 bg-zinc-900/20 backdrop-blur-[1px] lg:bg-transparent lg:backdrop-blur-none"
        onClick={onClose}
      />
      <aside
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[420px] flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-700 dark:bg-zinc-900"
        aria-label="Transaction details"
      >
        <div className="flex items-start justify-between gap-3 border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">Transaction</p>
            <h2 className="mt-1 truncate text-[18px] font-semibold text-zinc-900 dark:text-zinc-50">
              {record.record_id}
            </h2>
            <p className="mt-1 text-[12.5px] text-zinc-500">{record.tier_name}</p>
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
          >
            <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.5">
              <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="rounded-xl border border-zinc-200/80 bg-zinc-50/60 p-4 dark:border-zinc-700 dark:bg-zinc-800/40">
            <p className="text-[26px] font-semibold tabular-nums tracking-tight text-zinc-900 dark:text-zinc-50">
              {formatINR(record.expected || record.received)}
            </p>
            <div className="mt-3">
              <span
                className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${transactionStatusBadgeClass(uiStatus)}`}
              >
                {transactionStatusLabel(uiStatus)}
              </span>
            </div>
            {uiStatus === 'resolved' && linkedCase && (
              <p className="mt-3 text-[12.5px] text-teal-700 dark:text-teal-300">
                {linkedCase.resolution.resolution_type === 'auto_resolved'
                  ? 'Closed automatically — see the reason below.'
                  : 'Resolved by a reviewer — see the reason below.'}
              </p>
            )}
          </div>

          <section className="mt-6">
            <h3 className="text-[12px] font-semibold uppercase tracking-wide text-zinc-400">Amounts</h3>
            <div className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
              <DetailRow label="Expected" value={formatINR(record.expected)} />
              <DetailRow label="Received" value={formatINR(record.received)} />
              <DetailRow
                label="Delta"
                value={record.delta === 0 ? '—' : formatINR(record.delta)}
              />
              {fields.amountAtRisk > 0 && (
                <DetailRow label="At risk" value={formatINR(fields.amountAtRisk)} />
              )}
            </div>
          </section>

          <section className="mt-6">
            <h3 className="text-[12px] font-semibold uppercase tracking-wide text-zinc-400">
              Reconciliation
            </h3>
            <div className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
              {record.order_date && (
                <DetailRow label="Order date" value={formatCaseDate(record.order_date)} />
              )}
              {record.payment_mode && (
                <DetailRow label="Payment mode" value={record.payment_mode.replace(/_/g, ' ')} />
              )}
              {/* This is engine.py's own tier output from its last pass -- it
                  never learns that a case built on top of it was later
                  resolved (see the reason/settlement rows below, which do). */}
              <DetailRow label="Engine status" value={record.status.replace(/_/g, ' ')} />
              <DetailRow label="Reason" value={fields.reasonLabel || '—'} />
              <DetailRow
                label="Matched settlement"
                value={fields.matchedSettlement || 'Not linked'}
              />
              {record.age_days !== null && (
                <DetailRow label="Order age" value={`${record.age_days} days`} />
              )}
              <DetailRow label="Priority" value={record.priority || '—'} />
            </div>
            {fields.explanation && (
              <p className="mt-3 text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-400">
                {fields.explanation}
              </p>
            )}
          </section>

          {record.case_id && (
            <section className="mt-6">
              <h3 className="text-[12px] font-semibold uppercase tracking-wide text-zinc-400">Case</h3>
              <p className="mt-2 text-[13px] text-zinc-600 dark:text-zinc-400">
                {showCaseLink
                  ? linkedCase
                    ? `Linked to case ${linkedCase.case_id}`
                    : `Case ${record.case_id}`
                  : uiStatus === 'awaiting_settlement'
                    ? 'Within the COD collection window — informational only, not in review yet'
                    : 'No open review case for this record'}
              </p>
            </section>
          )}
        </div>

        {showCaseLink && record.case_id && (
          <div className="border-t border-zinc-100 p-4 dark:border-zinc-800">
            <Link
              to={caseDetailPath(record.case_id, null)}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-blue-700"
            >
              View case
              <span aria-hidden>↗</span>
            </Link>
          </div>
        )}
      </aside>
    </>
  )
}
