import type { ReactNode } from 'react'
import { formatINR } from '../../lib/money'
import type { ReconciliationViewModel } from '../../lib/reconciliationFinancials'
import { aiReachedVerdict, needsInvestigation } from '../../lib/caseUtils'
import type { Case } from '../../types/case'

function IconBox({ children, className }: { children: ReactNode; className: string }) {
  return (
    <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${className}`}>
      {children}
    </span>
  )
}

function MetricCard({
  icon,
  iconBg,
  label,
  value,
  sub,
}: {
  icon: ReactNode
  iconBg: string
  label: string
  value: string
  sub: string
}) {
  return (
    <div className="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <IconBox className={iconBg}>{icon}</IconBox>
      <p className="mt-3 text-[12px] text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="mt-0.5 text-[22px] font-semibold tabular-nums tracking-tight text-zinc-900 dark:text-zinc-50">
        {value}
      </p>
      <p className="mt-0.5 text-[11.5px] text-zinc-400 dark:text-zinc-500">{sub}</p>
    </div>
  )
}

type SummaryBoxesProps = {
  model: ReconciliationViewModel
  cases: Case[]
}

export function SummaryBoxes({ model, cases }: SummaryBoxesProps) {
  const { totals, orderCount, settlementCount } = model

  // Counted over CASES, not engine records, and split by WHAT AI CONCLUDED.
  // AI investigates every eligible case; the useful distinction is whether it
  // landed on something actionable. The two buckets are exclusive and sum to
  // the review queue, so these cards and the queue below always agree.
  const aiVerdict = cases.filter(aiReachedVerdict).length
  const manual = cases.filter(needsInvestigation).length
  const openTotal = aiVerdict + manual
  const share = (n: number) =>
    openTotal > 0 ? `${Math.round((n / openTotal) * 100)}% of open cases` : 'No open cases'

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        iconBg="bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400"
        icon={
          <svg viewBox="0 0 20 20" fill="none" className="h-[18px] w-[18px]" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="4" width="14" height="12" rx="1.5" />
            <path d="M3 8h14M7 2.5v3M13 2.5v3" strokeLinecap="round" />
          </svg>
        }
        label="Expected"
        value={formatINR(totals.expectedPaise)}
        // "records", not "orders": this count includes orphan bank credits,
        // which are reconciled records with no order behind them.
        sub={`${orderCount} records`}
      />
      <MetricCard
        iconBg="bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400"
        icon={
          <svg viewBox="0 0 20 20" fill="none" className="h-[18px] w-[18px]" stroke="currentColor" strokeWidth="1.5">
            <path d="M4 10l4 4 8-8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
        label="Received"
        value={formatINR(totals.receivedPaise)}
        sub={`${settlementCount} settlements`}
      />
      <MetricCard
        iconBg="bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-400"
        icon={
          <svg viewBox="0 0 20 20" fill="none" className="h-[18px] w-[18px]" stroke="currentColor" strokeWidth="1.5">
            <path d="M10 3l1.2 3.6H15l-3 2.2 1.2 3.6L10 10.2 6.8 12.4 8 9.8 5 7.6h3.8L10 3z" strokeLinejoin="round" />
          </svg>
        }
        label="AI recommendation"
        value={String(aiVerdict)}
        sub={share(aiVerdict)}
      />
      <MetricCard
        iconBg="bg-orange-50 text-orange-600 dark:bg-orange-500/15 dark:text-orange-400"
        icon={
          <svg viewBox="0 0 20 20" fill="none" className="h-[18px] w-[18px]" stroke="currentColor" strokeWidth="1.5">
            <path d="M10 4.5v6M10 13.5v0" strokeLinecap="round" />
            <circle cx="10" cy="10" r="7.5" />
          </svg>
        }
        label="Needs investigation"
        value={String(manual)}
        sub={share(manual)}
      />
    </div>
  )
}
