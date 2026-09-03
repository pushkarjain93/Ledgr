import type { OutcomeSegment } from '../../lib/reconciliationFinancials'

function InfoIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5 text-zinc-400" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="6" />
      <path d="M8 7v4M8 5.5v0" strokeLinecap="round" />
    </svg>
  )
}

const DASH = '–'

function DonutChart({
  segments,
  total,
  pending = false,
}: {
  segments: OutcomeSegment[]
  total: number
  pending?: boolean
}) {
  const size = 128
  const stroke = 18
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          {pending ? (
            // A flat neutral ring reads as "not known yet" -- an empty or
            // all-one-color ring built from real segment data would instead
            // read as "zero of everything", which is a different (false)
            // claim while AI is still mid-investigation.
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              className="stroke-zinc-200 dark:stroke-zinc-700"
              strokeWidth={stroke}
            />
          ) : (
            segments.map((seg) => {
              const dash = total > 0 ? (seg.count / total) * circumference : 0
              const circle = (
                <circle
                  key={seg.key}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={seg.color}
                  strokeWidth={stroke}
                  strokeDasharray={`${dash} ${circumference}`}
                  strokeDashoffset={-offset}
                  strokeLinecap="butt"
                />
              )
              offset += dash
              return circle
            })
          )}
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-[22px] font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
          {pending ? DASH : total}
        </span>
        <span className="text-[10px] text-zinc-500 dark:text-zinc-400">Total Records</span>
      </div>
    </div>
  )
}

type ReconciliationOutcomePanelProps = {
  segments: OutcomeSegment[]
  total: number
  pending?: boolean
}

export function ReconciliationOutcomePanel({
  segments,
  total,
  pending = false,
}: ReconciliationOutcomePanelProps) {
  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <div className="flex items-center gap-1.5">
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Reconciliation Outcome</h2>
        <InfoIcon />
      </div>

      <div className="mt-5 flex flex-1 flex-wrap items-center justify-center gap-6 lg:justify-start">
        <DonutChart segments={segments} total={total} pending={pending} />
        <ul className="min-w-[160px] space-y-2.5">
          {segments.map((seg) => (
            <li key={seg.key} className="flex items-center justify-between gap-4 text-[12.5px]">
              <span className="flex items-center gap-2 text-zinc-600 dark:text-zinc-300">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: seg.color }} />
                {seg.label}
              </span>
              <span className="tabular-nums text-zinc-800 dark:text-zinc-100">
                {pending ? (
                  <span className="font-semibold">{DASH}</span>
                ) : (
                  <>
                    <span className="font-semibold">{seg.count}</span>
                    <span className="text-zinc-400 dark:text-zinc-500"> ({seg.pct}%)</span>
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
