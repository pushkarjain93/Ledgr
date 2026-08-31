import { Link } from 'react-router-dom'
import { formatINR } from '../../lib/money'
import type { Case } from '../../types/case'

/**
 * The courier's own remittance paperwork behind a bulk COD payout.
 *
 * A bulk credit arrives as one line in the bank ("UTR… → ₹3,410.56") and on
 * its own cannot say which orders it covers. The courier publishes a per-order
 * breakdown alongside it, and this panel shows that breakdown — which is the
 * difference between "we matched this" and "trust us, we matched this".
 *
 * Renders nothing unless this case actually has remittance detail, so it never
 * appears as an empty placeholder on the vast majority of cases.
 */
function Row({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="text-[12.5px] text-zinc-500 dark:text-zinc-400">{label}</span>
      <span
        className={`text-[13px] tabular-nums ${
          muted
            ? 'text-zinc-500 dark:text-zinc-400'
            : 'font-medium text-zinc-900 dark:text-zinc-50'
        }`}
      >
        {value}
      </span>
    </div>
  )
}

export function CaseRemittancePanel({ caseItem }: { caseItem: Case }) {
  const r = caseItem.remittance
  const batch = caseItem.remittance_batch
  const findings = caseItem.remittance_findings ?? []

  if (!r && !batch && findings.length === 0) return null

  return (
    <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">
        Courier remittance detail
      </h2>
      <p className="mt-0.5 text-[12.5px] text-zinc-500 dark:text-zinc-400">
        From the courier&apos;s own remittance file — matched on order ID, not estimated.
      </p>

      {/* Order side: this order's share of a bulk payout. */}
      {r && (
        <div className="mt-4 space-y-2.5">
          <Row label="Courier" value={r.courier} />
          <Row label="Remitted on" value={r.remitted_on} />
          <Row label="Bank reference (UTR)" value={r.utr} muted />
          {r.awb && <Row label="AWB" value={r.awb} muted />}
          <div className="mt-3 space-y-2.5 border-t border-zinc-100 pt-3 dark:border-zinc-800">
            <Row label="Collected from customer" value={formatINR(r.cod_collected)} />
            <Row
              label="Courier fees"
              value={`− ${formatINR(r.cod_fee + r.freight_fee)}`}
              muted
            />
            <Row label="Paid out to you" value={formatINR(r.net_payout)} />
          </div>
          <p className="pt-1 text-[12px] leading-relaxed text-zinc-500 dark:text-zinc-400">
            One of {r.batch_order_count} orders in a single {formatINR(r.batch_credit)} bank
            credit.
          </p>
        </div>
      )}

      {/* Settlement side: what this one bank credit turned out to be. */}
      {batch && (
        <div className="mt-4 space-y-2.5">
          <Row label="Courier" value={batch.courier} />
          <Row label="Remitted on" value={batch.remitted_on} />
          <Row label="Bank reference (UTR)" value={batch.utr} muted />
          <div className="mt-3 space-y-2.5 border-t border-zinc-100 pt-3 dark:border-zinc-800">
            <Row label="Orders in this batch" value={String(batch.order_count)} />
            <Row label="Remittance rows total" value={formatINR(batch.rows_total)} />
            <Row label="Bank credit received" value={formatINR(batch.credit_amount)} />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {batch.order_ids.map((id) => (
              <Link
                key={id}
                to={`/transactions?search=${encodeURIComponent(id)}&from=${encodeURIComponent(caseItem.case_id)}`}
                className="rounded-md bg-zinc-100 px-2 py-0.5 text-[12px] font-medium text-zinc-700 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
              >
                {id}
              </Link>
            ))}
          </div>
        </div>
      )}

      {findings.length > 0 && (
        <ul className="mt-4 space-y-2 border-t border-zinc-100 pt-4 dark:border-zinc-800">
          {findings.map((f) => (
            <li
              key={f.kind + f.detail}
              className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] leading-relaxed text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/25 dark:text-amber-200"
            >
              {f.detail}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
