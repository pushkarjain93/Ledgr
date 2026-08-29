import { useState } from 'react'
import type { RunChartPoint } from '../../lib/reconciliationMetrics'

const BAR_FILL = '#bfdbfe'
const BAR_FILL_ACTIVE = '#3b82f6'
const BAR_FILL_HOVER = '#93c5fd'

type ReconciliationChartProps = {
  runs: RunChartPoint[]
}

export function ReconciliationChart({ runs }: ReconciliationChartProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hoverId, setHoverId] = useState<string | null>(null)

  const selected = runs.find((r) => r.runId === selectedId) ?? null

  if (runs.length === 0) {
    return (
      <section className="rounded-2xl border border-zinc-200 bg-white p-6">
        <h2 className="text-[15px] font-semibold text-zinc-900">Reconciliation by run</h2>
        <p className="mt-0.5 text-[12.5px] text-zinc-500">Records processed per completed run</p>
        <div className="mt-8 flex h-[180px] items-center justify-center rounded-xl border border-dashed border-zinc-200 bg-zinc-50 text-[13px] text-zinc-400">
          No runs on this date — use Sync &amp; Reconcile to start
        </div>
      </section>
    )
  }

  const maxRecords = Math.max(...runs.map((r) => r.totalRecords), 1)
  const chartH = 160
  const barW = runs.length === 1 ? 80 : Math.min(100, 280 / runs.length)

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-6">
      <h2 className="text-[15px] font-semibold text-zinc-900">Reconciliation by run</h2>
      <p className="mt-0.5 text-[12.5px] text-zinc-500">Click a bar to see records processed</p>

      <div className="mt-6 overflow-x-auto">
        <svg
          viewBox={`0 0 ${Math.max(runs.length * (barW + 48), 320)} ${chartH + 56}`}
          className="w-full min-w-[320px]"
          role="list"
        >
          {runs.map((run, i) => {
            const h = (run.totalRecords / maxRecords) * chartH
            const x = 40 + i * (barW + 48)
            const y = chartH - h + 8
            const isSelected = selectedId === run.runId
            const isHover = hoverId === run.runId

            return (
              <g key={run.runId} role="listitem">
                <rect
                  x={x}
                  y={y}
                  width={barW}
                  height={Math.max(h, 4)}
                  rx={8}
                  fill={isSelected ? BAR_FILL_ACTIVE : isHover ? BAR_FILL_HOVER : BAR_FILL}
                  className="cursor-pointer"
                  onClick={() =>
                    setSelectedId((prev) => (prev === run.runId ? null : run.runId))
                  }
                  onMouseEnter={() => setHoverId(run.runId)}
                  onMouseLeave={() => setHoverId(null)}
                />
                {(isSelected || isHover) && (
                  <text
                    x={x + barW / 2}
                    y={y - 8}
                    textAnchor="middle"
                    fill="#1d4ed8"
                    style={{ fontSize: 11, fontWeight: 600 }}
                  >
                    {run.totalRecords}
                  </text>
                )}
                <text x={x + barW / 2} y={chartH + 26} textAnchor="middle" fill="#71717a" style={{ fontSize: 10 }}>
                  {run.label}
                </text>
                <text x={x + barW / 2} y={chartH + 40} textAnchor="middle" fill="#a1a1aa" style={{ fontSize: 10 }}>
                  {run.dateLabel}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {selected ? (
        <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3">
          <p className="text-[13px] font-medium text-zinc-800">
            {selected.label} · {selected.dateLabel} at {selected.timeLabel}
          </p>
          <p className="mt-1 text-[22px] font-semibold text-blue-700">
            {selected.totalRecords}{' '}
            <span className="text-[14px] font-normal text-zinc-500">records processed</span>
          </p>
        </div>
      ) : (
        <p className="mt-4 text-[12px] text-zinc-400">Select a bar to view record count</p>
      )}
    </section>
  )
}

type ImprovementChartProps = {
  latest: RunChartPoint | null
  previous: RunChartPoint | null
  aiContributionDelta: number | null
}

export function ImprovementChart({
  latest,
  previous,
  aiContributionDelta,
}: ImprovementChartProps) {
  if (!latest || !previous) {
    return (
      <section className="rounded-2xl border border-zinc-200 bg-white p-6">
        <h2 className="text-[15px] font-semibold text-zinc-900">AI contribution</h2>
        <p className="mt-0.5 text-[12.5px] text-zinc-500">Share of records resolved with AI assistance</p>
        <div className="mt-8 flex h-[180px] items-center justify-center rounded-xl border border-dashed border-zinc-200 bg-zinc-50 text-[13px] text-zinc-400">
          Needs at least two runs on this date to compare
        </div>
      </section>
    )
  }

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold text-zinc-900">AI contribution</h2>
          <p className="mt-0.5 text-[12.5px] text-zinc-500">
            Share of records resolved with AI assistance (%)
          </p>
        </div>
        {aiContributionDelta !== null && (
          <span
            className={`rounded-lg px-2.5 py-1 text-[12px] font-medium ${
              aiContributionDelta >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-orange-50 text-orange-700'
            }`}
          >
            {aiContributionDelta >= 0 ? '+' : ''}
            {aiContributionDelta}% vs previous
          </span>
        )}
      </div>

      <p className="mt-1 text-[12px] text-zinc-400">
        {previous.label} → {latest.label}
      </p>

      <div className="mt-6 space-y-5">
        {[
          { label: previous.label, pct: previous.aiContributionPct, sub: 'Previous run' },
          { label: latest.label, pct: latest.aiContributionPct, sub: 'Latest run' },
        ].map(({ label, pct, sub }) => (
          <div key={label}>
            <div className="mb-2 flex justify-between text-[12px]">
              <span className="text-zinc-500">{sub} · {label}</span>
              <span className="font-medium text-zinc-700">{pct}%</span>
            </div>
            <div className="h-8 overflow-hidden rounded-lg bg-zinc-100">
              <div
                className="h-full rounded-lg bg-violet-500 transition-all duration-300"
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <p className="mt-1 text-[11px] text-zinc-400">
              {label === previous.label ? previous.aiResolved : latest.aiResolved} of{' '}
              {label === previous.label ? previous.totalRecords : latest.totalRecords} records
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
