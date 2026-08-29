import { formatINR } from '../../lib/money'
import { formatCaseDate } from '../../lib/caseDisplay'
import { issueTypeLabel } from '../../lib/caseUtils'
import type { Case } from '../../types/case'

type CaseSummaryPanelProps = {
  caseItem: Case
}

function SummaryRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <span className="text-[13px] text-zinc-500">{label}</span>
      <span
        className={`text-right text-[13px] font-medium tabular-nums ${
          highlight ? 'text-red-600 dark:text-red-400' : 'text-zinc-900 dark:text-zinc-100'
        }`}
      >
        {value}
      </span>
    </div>
  )
}

export function CaseSummaryPanel({ caseItem }: CaseSummaryPanelProps) {
  const difference = caseItem.expected - caseItem.received

  return (
    <section
      id="case-summary"
      className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900"
    >
      <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Case Summary</h2>

      <div className="mt-4 divide-y divide-zinc-100 dark:divide-zinc-800">
        <SummaryRow label="Expected amount" value={formatINR(caseItem.expected)} />
        <SummaryRow label="Received amount" value={formatINR(caseItem.received)} />
        <SummaryRow
          label="Difference"
          value={formatINR(Math.abs(difference))}
          highlight={difference !== 0}
        />
      </div>

      <div className="mt-4 space-y-2 border-t border-zinc-100 pt-4 dark:border-zinc-800">
        <SummaryRow label="Issue type" value={issueTypeLabel(caseItem.case_type)} />
        <SummaryRow label="Order date" value={formatCaseDate(caseItem.order_date || caseItem.created_at)} />
        <SummaryRow
          label="Customer"
          value={caseItem.customer_name?.trim() || '—'}
        />
        <SummaryRow label="Order ID" value={caseItem.order_id ?? '—'} />
        <SummaryRow label="Settlement ID" value={caseItem.settlement_id ?? '—'} />
        <SummaryRow label="Priority" value={caseItem.priority || '—'} />
      </div>

      {caseItem.explanation && (
        <p className="mt-4 rounded-lg bg-zinc-50 px-3 py-2.5 text-[12.5px] leading-relaxed text-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-300">
          {caseItem.explanation}
        </p>
      )}
    </section>
  )
}
