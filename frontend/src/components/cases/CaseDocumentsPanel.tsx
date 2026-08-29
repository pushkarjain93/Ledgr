import { useEffect, useState } from 'react'
import { api, type CaseEvidence } from '../../lib/api'
import { formatINR } from '../../lib/money'

/**
 * Supporting Documents — the real records behind a case.
 *
 * Each entry opens the actual underlying data from GET /api/cases/{id}/evidence,
 * which reads the same orders.csv / settlements.csv the engine reconciled.
 * A document is only listed when its record genuinely exists: an orphan
 * settlement has no order, an unmatched order has no settlement, and neither
 * gets an empty placeholder.
 */
type DocKey = 'order' | 'settlement' | 'fee' | 'activity'

type CaseDocumentsPanelProps = {
  caseId: string
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-zinc-100 py-2 last:border-b-0 dark:border-zinc-800">
      <span className="shrink-0 text-[12.5px] text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className="text-right text-[13px] font-medium text-zinc-900 dark:text-zinc-100">
        {value || '—'}
      </span>
    </div>
  )
}

export function CaseDocumentsPanel({ caseId }: CaseDocumentsPanelProps) {
  const [evidence, setEvidence] = useState<CaseEvidence | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<DocKey | null>(null)

  useEffect(() => {
    let cancelled = false
    setEvidence(null)
    setError(null)
    setOpen(null)
    api
      .getCaseEvidence(caseId)
      .then((e) => !cancelled && setEvidence(e))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : 'Failed to load'))
    return () => {
      cancelled = true
    }
  }, [caseId])

  // Escape closes the open document.
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(null)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  // Only list what actually exists behind this case.
  const docs: { key: DocKey; label: string }[] = []
  if (evidence?.order) docs.push({ key: 'order', label: 'Order Details' })
  if (evidence?.settlement) docs.push({ key: 'settlement', label: 'Settlement Details' })
  if (evidence?.fee_structure) docs.push({ key: 'fee', label: 'Fee Structure (MDR)' })
  if (evidence?.history?.length) docs.push({ key: 'activity', label: 'Activity Log' })

  return (
    <>
      <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">
          Supporting Documents
        </h2>

        {error ? (
          <p className="mt-3 text-[13px] text-zinc-500 dark:text-zinc-400">
            Could not load supporting records.
          </p>
        ) : !evidence ? (
          <p className="mt-3 text-[13px] text-zinc-400 dark:text-zinc-500">Loading…</p>
        ) : docs.length === 0 ? (
          <p className="mt-3 text-[13px] text-zinc-500 dark:text-zinc-400">
            No supporting records available for this case.
          </p>
        ) : (
          <ul className="mt-4 space-y-2">
            {docs.map(({ key, label }) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => setOpen(key)}
                  className="text-[13px] font-medium text-blue-600 hover:underline dark:text-blue-400"
                >
                  {label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {open && evidence && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => setOpen(null)}
        >
          <div
            className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-700 dark:bg-zinc-900"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-4">
              <h3 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">
                {docs.find((d) => d.key === open)?.label}
              </h3>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setOpen(null)}
                className="rounded-md px-2 text-[18px] leading-none text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
              >
                ×
              </button>
            </div>

            {open === 'order' && evidence.order && (
              <div>
                <Row label="Order ID" value={evidence.order.order_id} />
                <Row label="Order date" value={evidence.order.order_date} />
                <Row label="Customer" value={evidence.order.customer_name} />
                <Row label="Phone" value={evidence.order.customer_phone} />
                <Row label="Email" value={evidence.order.customer_email} />
                <Row label="Amount" value={formatINR(evidence.order.amount)} />
                <Row label="Payment mode" value={evidence.order.payment_mode} />
                <Row label="Gateway ref" value={evidence.order.gateway_ref_id} />
                <Row label="Bank UTR" value={evidence.order.bank_utr} />
                <Row label="Courier" value={evidence.order.courier} />
                <Row label="Source" value={evidence.order.source} />
              </div>
            )}

            {open === 'settlement' && evidence.settlement && (
              <div>
                <Row label="Settlement ID" value={evidence.settlement.settlement_id} />
                <Row label="Settled on" value={evidence.settlement.settled_on} />
                <Row label="Amount received" value={formatINR(evidence.settlement.amount_received)} />
                <Row label="Gateway ref" value={evidence.settlement.gateway_ref_id} />
                <Row label="Bank UTR" value={evidence.settlement.bank_utr} />
                <Row label="Source" value={evidence.settlement.source} />
                <Row label="Narration" value={evidence.settlement.narration} />
              </div>
            )}

            {open === 'fee' && evidence.fee_structure && (
              <div>
                <Row label="Payment mode" value={evidence.fee_structure.payment_mode} />
                <Row
                  label="Tolerance rule"
                  value={`${(evidence.fee_structure.tolerance_pct * 100).toFixed(1)}% of order, or ${formatINR(
                    evidence.fee_structure.tolerance_flat,
                  )} flat — whichever is larger`}
                />
                <Row label="Order amount" value={formatINR(evidence.fee_structure.order_amount)} />
                <Row
                  label="Max explainable shortfall"
                  value={formatINR(evidence.fee_structure.max_explainable_shortfall)}
                />
                {evidence.fee_structure.comparable ? (
                  <>
                    <Row
                      label="This case's shortfall"
                      value={formatINR(evidence.fee_structure.actual_shortfall ?? 0)}
                    />
                    <Row
                      label="Within fee band?"
                      value={evidence.fee_structure.within_band ? 'Yes' : 'No — exceeds normal fees'}
                    />
                  </>
                ) : (
                  <Row label="This case's shortfall" value="No settlement received yet" />
                )}
                <p className="mt-3 text-[12px] leading-relaxed text-zinc-500 dark:text-zinc-400">
                  {evidence.fee_structure.comparable
                    ? 'The same tolerance rule the reconciliation engine uses to auto-clear known fee deductions.'
                    : 'Nothing has settled against this order, so there is no shortfall to compare against the fee band yet.'}
                </p>
              </div>
            )}

            {open === 'activity' && (
              <ol className="space-y-3">
                {evidence.history.map((h, i) => (
                  <li key={`${h.at}-${i}`} className="flex gap-3">
                    <span className="shrink-0 text-[12px] text-zinc-400 dark:text-zinc-500">
                      {new Date(h.at).toLocaleString('en-IN', {
                        day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
                      })}
                    </span>
                    <span className="text-[13px] text-zinc-800 dark:text-zinc-200">{h.event}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      )}
    </>
  )
}
