import { useEffect, useMemo, useState } from 'react'
import {
  buildReconciliationGraphSeries,
  type ReconciliationGraphPoint,
  type RunChartPoint,
} from '../../lib/reconciliationMetrics'
import { periodLabel, type ReconciliationPeriod } from '../../lib/merchantState'
import type { ReconciliationRun } from '../../types/case'

const LINE_STROKE = '#27272a'
const LINE_FILL = 'rgba(39, 39, 42, 0.08)'
const GRID_STROKE = '#e4e4e7'
const POINT_FILL = '#ffffff'
const POINT_STROKE = '#27272a'
const POINT_ACTIVE = '#27272a'

const PERIOD_OPTIONS: { value: ReconciliationPeriod; label: string }[] = [
  { value: 'day', label: 'Day' },
  { value: 'month', label: 'Month' },
  { value: 'year', label: 'Year' },
]

type ReconciliationChartProps = {
  allRuns: ReconciliationRun[]
  referenceDate: string
}

function PeriodSelect({
  period,
  onChange,
}: {
  period: ReconciliationPeriod
  onChange: (period: ReconciliationPeriod) => void
}) {
  return (
    <select
      value={period}
      onChange={(e) => onChange(e.target.value as ReconciliationPeriod)}
      aria-label="Reconciliation period"
      className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-[12.5px] font-medium text-zinc-700 outline-none ring-blue-500/0 transition-colors hover:border-zinc-300 focus:ring-2 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:border-zinc-500"
    >
      {PERIOD_OPTIONS.map(({ value, label }) => (
        <option key={value} value={value}>
          {label}
        </option>
      ))}
    </select>
  )
}

function formatAxisValue(value: number): string {
  if (value >= 1000) return `${Math.round(value / 100) / 10}k`
  return String(value)
}

function ReconciliationLineGraph({
  points,
  period,
}: {
  points: ReconciliationGraphPoint[]
  period: ReconciliationPeriod
}) {
  const [hoverId, setHoverId] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const activeId = hoverId ?? selectedId
  const active = points.find((point) => point.id === activeId) ?? null
  const hasData = points.some((point) => point.totalRecords > 0)

  const padding = { top: 24, right: 16, bottom: 44, left: 44 }
  const width = 560
  const height = 220
  const plotW = width - padding.left - padding.right
  const plotH = height - padding.top - padding.bottom

  const maxValue = Math.max(...points.map((point) => point.totalRecords), 1)
  const yTicks = [0, Math.round(maxValue / 2), maxValue]

  const coords = points.map((point, index) => {
    const x =
      points.length === 1
        ? padding.left + plotW / 2
        : padding.left + (index / (points.length - 1)) * plotW
    const y = padding.top + plotH - (point.totalRecords / maxValue) * plotH
    return { point, x, y }
  })

  const linePath = coords
    .map(({ x, y }, index) => `${index === 0 ? 'M' : 'L'} ${x} ${y}`)
    .join(' ')

  const areaPath =
    coords.length > 0
      ? `${linePath} L ${coords.at(-1)!.x} ${padding.top + plotH} L ${coords[0].x} ${padding.top + plotH} Z`
      : ''

  const labelStep =
    period === 'month' ? Math.ceil(points.length / 8) : period === 'year' ? 1 : 1

  return (
    <div>
      <p className="mt-2 text-[12px] text-zinc-400 dark:text-zinc-500">
        Hover a point to see records processed · click to pin details
      </p>

      <div className="mt-3 min-h-[22px] text-[13px] font-medium text-zinc-700 dark:text-zinc-200" aria-live="polite">
        {active ? (
          <>
            {active.subLabel ? `${active.subLabel} · ` : ''}
            {active.label} ·{' '}
            <span className="tabular-nums text-zinc-900 dark:text-zinc-50">
              {active.totalRecords} records
              {active.runCount > 1 ? ` across ${active.runCount} runs` : ''}
            </span>
          </>
        ) : (
          <span className="text-zinc-400 dark:text-zinc-500">
            {hasData ? 'Hover the graph to preview' : 'No activity in this period'}
          </span>
        )}
      </div>

      <div className="mt-3 overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[320px]" role="img" aria-label="Reconciliation trend graph">
          {yTicks.map((tick) => {
            const y = padding.top + plotH - (tick / maxValue) * plotH
            return (
              <g key={tick}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={padding.left + plotW}
                  y2={y}
                  stroke={GRID_STROKE}
                  strokeDasharray="4 4"
                />
                <text
                  x={padding.left - 8}
                  y={y + 4}
                  textAnchor="end"
                  fill="#a1a1aa"
                  style={{ fontSize: 10 }}
                >
                  {formatAxisValue(tick)}
                </text>
              </g>
            )
          })}

          {hasData && areaPath ? (
            <path d={areaPath} fill={LINE_FILL} stroke="none" />
          ) : null}

          {hasData && linePath ? (
            <path
              d={linePath}
              fill="none"
              stroke={LINE_STROKE}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ) : null}

          {coords.map(({ point, x, y }) => {
            const isActive = activeId === point.id
            const hasPoint = point.totalRecords > 0
            return (
              <g key={point.id}>
                <circle
                  cx={x}
                  cy={y}
                  r={14}
                  fill="transparent"
                  className={hasPoint ? 'cursor-pointer' : undefined}
                  onMouseEnter={() => hasPoint && setHoverId(point.id)}
                  onMouseLeave={() => setHoverId(null)}
                  onClick={() => hasPoint && setSelectedId((prev) => (prev === point.id ? null : point.id))}
                />
                {hasPoint ? (
                  <circle
                    cx={x}
                    cy={y}
                    r={isActive ? 5 : 3.5}
                    fill={isActive ? POINT_ACTIVE : POINT_FILL}
                    stroke={POINT_STROKE}
                    strokeWidth={2}
                    className="cursor-pointer"
                    onMouseEnter={() => setHoverId(point.id)}
                    onMouseLeave={() => setHoverId(null)}
                    onClick={() => setSelectedId((prev) => (prev === point.id ? null : point.id))}
                  >
                    <title>{`${point.label}: ${point.totalRecords} records`}</title>
                  </circle>
                ) : null}
              </g>
            )
          })}

          {coords.map(({ point, x }, index) => {
            if (index % labelStep !== 0 && index !== coords.length - 1) return null
            return (
              <text
                key={`${point.id}-label`}
                x={x}
                y={height - 16}
                textAnchor="middle"
                fill="#71717a"
                style={{ fontSize: 10 }}
              >
                {point.label}
              </text>
            )
          })}
        </svg>
      </div>

      {active && active.totalRecords > 0 ? (
        <div className="mt-4 rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-700 dark:bg-zinc-800/50">
          <p className="text-[13px] font-medium text-zinc-800 dark:text-zinc-100">
            {active.subLabel ? `${active.subLabel} · ` : ''}
            {active.label}
          </p>
          <p className="mt-1 text-[22px] font-semibold text-zinc-900 dark:text-zinc-50">
            {active.totalRecords}{' '}
            <span className="text-[14px] font-normal text-zinc-500 dark:text-zinc-400">records processed</span>
          </p>
          {active.runCount > 0 ? (
            <p className="mt-1 text-[12px] text-zinc-500 dark:text-zinc-400">
              {/* The graph bucket aggregates whole runs, so it carries no
                  awaiting-settlement split. Stating auto-matched against the
                  total avoids implying every other record needs review. */}
              {active.autoMatched} auto matched of {active.totalRecords} records
            </p>
          ) : null}
        </div>
      ) : (
        <p className="mt-4 text-[12px] text-zinc-400 dark:text-zinc-500">Click a point to pin details</p>
      )}
    </div>
  )
}

export function ReconciliationChart({ allRuns, referenceDate }: ReconciliationChartProps) {
  const [period, setPeriod] = useState<ReconciliationPeriod>('day')

  const points = useMemo(
    () => buildReconciliationGraphSeries(allRuns, period, referenceDate),
    [allRuns, period, referenceDate],
  )

  const rangeLabel = periodLabel(period, referenceDate)
  const hasData = points.some((point) => point.totalRecords > 0)

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-700 dark:bg-zinc-900">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Reconciliation trend</h2>
          <p className="mt-0.5 text-[12.5px] text-zinc-500 dark:text-zinc-400">{rangeLabel}</p>
        </div>
        <PeriodSelect period={period} onChange={setPeriod} />
      </div>

      {!hasData ? (
        <div className="mt-8 flex h-[220px] items-center justify-center rounded-xl border border-dashed border-zinc-200 bg-zinc-50 text-[13px] text-zinc-400 dark:border-zinc-700 dark:bg-zinc-800/50">
          No reconciliation data for this {period}
        </div>
      ) : (
        <ReconciliationLineGraph key={`${period}-${referenceDate}`} points={points} period={period} />
      )}
    </section>
  )
}

type ManualWorkEliminatedCardProps = {
  runs: RunChartPoint[]
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500">
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-emerald-600" />
        Auto matched
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-violet-600" />
        Awaiting settlement
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-orange-400" />
        Needs review
      </span>
    </div>
  )
}

function EliminationBar({ run, compact = false }: { run: RunChartPoint; compact?: boolean }) {
  const eliminatedPct = run.manualWorkEliminationPct
  const manualPct = run.manualWorkRemainingPct
  // The green band is settled-with-no-case; violet is COD still inside its
  // window. Previously violet showed AI-diagnosed records INSIDE the
  // "eliminated" portion, which double-claimed work that still needed review.
  const autoShare = 100
  const aiShare = 0

  return (
    <div>
      <div
        className={`flex overflow-hidden rounded-full bg-orange-100 dark:bg-orange-950/30 ${
          compact ? 'h-2.5' : 'h-3.5'
        }`}
      >
        {eliminatedPct > 0 && (
          <div className="flex h-full" style={{ width: `${eliminatedPct}%` }}>
            {run.autoMatchedPct > 0 && (
              <div
                className="h-full bg-emerald-600 dark:bg-emerald-500"
                style={{ width: `${autoShare}%` }}
              />
            )}
            {run.aiResolvedPct > 0 && (
              <div
                className="h-full bg-violet-600 dark:bg-violet-500"
                style={{ width: `${aiShare}%` }}
              />
            )}
          </div>
        )}
        {manualPct > 0 && (
          <div className="h-full bg-orange-400 dark:bg-orange-500/80" style={{ width: `${manualPct}%` }} />
        )}
      </div>
      {!compact && (
        <div className="mt-1.5 flex justify-between text-[10.5px] text-zinc-400">
          <span>Work eliminated</span>
          <span>Manual</span>
        </div>
      )}
    </div>
  )
}

function StatLine({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-4 text-[13px]">
      <span className="text-zinc-500">{label}</span>
      <span className="font-medium tabular-nums text-zinc-900 dark:text-zinc-100">{value}</span>
    </div>
  )
}

function RunBreakdownCard({ run }: { run: RunChartPoint }) {
  return (
    <div className="rounded-xl border border-zinc-100 bg-zinc-50/60 p-4 dark:border-zinc-800 dark:bg-zinc-800/30">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div>
          <p className="text-[13px] font-medium text-zinc-800 dark:text-zinc-100">
            Run {run.runNumber} · {run.dateLabel}
          </p>
          <p className="mt-0.5 text-[11px] text-zinc-400">{run.timeLabel}</p>
        </div>
        <p className="text-[13px] font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
          {run.manualWorkEliminationPct}% eliminated
        </p>
      </div>
      <EliminationBar run={run} compact />
      <p className="mt-2.5 text-[11.5px] text-zinc-500">
        {run.autoMatched} auto matched · {run.awaitingSettlement} awaiting · {run.aiResolved + run.exceptions} need review
      </p>
      <div className="mt-3 space-y-1.5 border-t border-zinc-100 pt-3 dark:border-zinc-700">
        <StatLine label="Auto matched" value={run.autoMatched} />
        <StatLine label="Awaiting settlement" value={run.awaitingSettlement} />
        <StatLine label="Needs review" value={run.aiResolved + run.exceptions} />
        <StatLine label="Total records" value={run.totalRecords} />
      </div>
    </div>
  )
}

function RunBreakdownOverlay({ runs, onClose }: { runs: RunChartPoint[]; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center">
      <button
        type="button"
        className="absolute inset-0 bg-zinc-900/40 backdrop-blur-[2px]"
        aria-label="Close run breakdown"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-labelledby="run-breakdown-title"
        aria-modal="true"
        className="relative flex max-h-[min(85vh,640px)] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xl dark:border-zinc-700 dark:bg-zinc-900"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
          <div>
            <h3 id="run-breakdown-title" className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">
              Run breakdown
            </h3>
            <p className="mt-0.5 text-[12.5px] text-zinc-500">{runs.length} runs on this date</p>
          </div>
          <button
            type="button"
            aria-label="Close"
            className="rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
            onClick={onClose}
          >
            <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.5">
              <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4">
          <div className="mb-4">
            <Legend />
          </div>
          <div className="space-y-3">
            {runs.map((run) => (
              <RunBreakdownCard key={run.runId} run={run} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function RunBreakdownSection({ runs }: { runs: RunChartPoint[] }) {
  const [open, setOpen] = useState(false)

  if (runs.length <= 1) return null

  return (
    <>
      <div className="mt-8 border-t border-zinc-100 pt-6 dark:border-zinc-800">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex w-full items-center justify-between gap-3 rounded-xl border border-zinc-200/80 bg-zinc-50/50 px-4 py-3 text-left transition-colors hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800/40 dark:hover:border-zinc-600"
        >
          <div>
            <h3 className="text-[12px] font-medium uppercase tracking-wide text-zinc-500">Run breakdown</h3>
            <p className="mt-0.5 text-[13px] text-zinc-700 dark:text-zinc-300">
              View all {runs.length} runs on this date
            </p>
          </div>
          <svg
            viewBox="0 0 16 16"
            fill="none"
            className="h-4 w-4 shrink-0 text-zinc-400"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden
          >
            <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      {open && <RunBreakdownOverlay runs={runs} onClose={() => setOpen(false)} />}
    </>
  )
}

export function ManualWorkEliminatedCard({ runs }: ManualWorkEliminatedCardProps) {
  const currentRun = runs.at(-1) ?? null

  if (!currentRun) {
    return (
      <section className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-700 dark:bg-zinc-900">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          Manual work eliminated
        </h2>
        <div className="mt-8 flex h-[200px] items-center justify-center rounded-xl border border-dashed border-zinc-200 bg-zinc-50 text-[13px] text-zinc-400 dark:border-zinc-700 dark:bg-zinc-800/50">
          No reconciliation run yet — sync to see results
        </div>
      </section>
    )
  }

  const pct = currentRun.manualWorkEliminationPct
  const breakdownRuns = [...runs].reverse()

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-700 dark:bg-zinc-900">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
        Manual work eliminated
      </p>

      <p className="mt-4 text-[48px] font-semibold leading-none tracking-tight tabular-nums text-zinc-900 dark:text-zinc-50">
        {pct}%
      </p>
      <p className="mt-3 max-w-sm text-[14px] leading-relaxed text-zinc-600 dark:text-zinc-300">
        This run eliminated {pct}% of manual reconciliation work.
      </p>

      <div className="mt-6 space-y-2 border-t border-zinc-100 pt-5 dark:border-zinc-800">
        <StatLine label="Auto matched" value={currentRun.autoMatched} />
        <StatLine label="Awaiting settlement" value={currentRun.awaitingSettlement} />
        <StatLine label="Needs review" value={currentRun.aiResolved + currentRun.exceptions} />
        <StatLine label="Total records" value={currentRun.totalRecords} />
      </div>

      <div className="mt-6">
        <EliminationBar run={currentRun} />
      </div>

      <div className="mt-4">
        <Legend />
      </div>

      <RunBreakdownSection runs={breakdownRuns} />
    </section>
  )
}
