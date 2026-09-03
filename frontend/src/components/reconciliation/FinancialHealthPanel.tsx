import { formatINR } from '../../lib/money'
import { barWidth, type ReconciliationViewModel } from '../../lib/reconciliationFinancials'

const DASH = '–'

function RiskCard({
  label,
  amountPaise,
  recordCount,
  tone,
  pending = false,
}: {
  label: string
  amountPaise: number
  recordCount: number
  tone: 'overpaid' | 'atRisk'
  pending?: boolean
}) {
  const styles =
    tone === 'overpaid'
      ? {
          wrap: 'bg-amber-50 dark:bg-amber-950/30',
          icon: 'bg-amber-100 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400',
          label: 'text-amber-700 dark:text-amber-300',
        }
      : {
          wrap: 'bg-red-50 dark:bg-red-950/30',
          icon: 'bg-red-100 text-red-600 dark:bg-red-500/20 dark:text-red-400',
          label: 'text-red-700 dark:text-red-300',
        }

  return (
    <div className={`rounded-xl p-4 ${styles.wrap}`}>
      <div className="flex items-start gap-3">
        <span
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${styles.icon}`}
        >
          {tone === 'overpaid' ? (
            <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 3v10M4 7h8" strokeLinecap="round" />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 4v5M8 11v1" strokeLinecap="round" />
              <circle cx="8" cy="8" r="6" />
            </svg>
          )}
        </span>
        <div>
          <p className={`text-[12px] font-medium ${styles.label}`}>{label}</p>
          <p className="mt-0.5 text-[18px] font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
            {pending ? DASH : formatINR(amountPaise)}
          </p>
          <p className="mt-0.5 text-[11px] text-zinc-500 dark:text-zinc-400">{recordCount} records</p>
        </div>
      </div>
    </div>
  )
}

type FinancialHealthPanelProps = {
  model: ReconciliationViewModel
  pending?: boolean
}

export function FinancialHealthPanel({ model, pending = false }: FinancialHealthPanelProps) {
  const { totals, overpaid, atRisk } = model
  const receivedW = barWidth(totals.receivedPaise, totals.expectedPaise)

  return (
    <div className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Financial health</h2>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_168px]">
        <div>
          {/* Expected */}
          <div className="flex items-center gap-4">
            <div className="w-[108px] shrink-0">
              <p className="text-[12px] text-zinc-500 dark:text-zinc-400">Expected</p>
              <p className="text-[14px] font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
                {pending ? DASH : formatINR(totals.expectedPaise)}
              </p>
            </div>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-blue-500" />
          </div>

          {/* Received */}
          <div className="mt-4 flex items-center gap-4">
            <div className="w-[108px] shrink-0">
              <p className="text-[12px] text-zinc-500 dark:text-zinc-400">Received</p>
              <p className="text-[14px] font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
                {pending ? DASH : formatINR(totals.receivedPaise)}
              </p>
            </div>
            <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
              <div
                className="absolute inset-y-0 left-0 rounded-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${receivedW}%` }}
              />
            </div>
          </div>

          {/* Difference */}
          <div className="mt-5 rounded-xl bg-blue-50 px-4 py-5 text-center dark:bg-blue-500/10">
            <p className="text-[12px] text-zinc-500 dark:text-zinc-400">Difference</p>
            <p className="mt-1 text-[24px] font-semibold tabular-nums tracking-tight text-zinc-900 dark:text-zinc-50">
              {pending ? DASH : formatINR(totals.differencePaise)}
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <RiskCard
            label="Overpaid"
            amountPaise={overpaid.amountPaise}
            recordCount={overpaid.recordCount}
            tone="overpaid"
            pending={pending}
          />
          <RiskCard
            label="At Risk"
            amountPaise={atRisk.amountPaise}
            recordCount={atRisk.recordCount}
            tone="atRisk"
            pending={pending}
          />
        </div>
      </div>
    </div>
  )
}
