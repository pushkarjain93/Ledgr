import { Link } from 'react-router-dom'
import type { ReconciliationDashboard } from '../../lib/reconciliationMetrics'

type StatsSegmentProps = {
  recon: ReconciliationDashboard
  needsDecisionCount: number
  openCasesCount: number
}

export function StatsSegment({ recon, needsDecisionCount, openCasesCount }: StatsSegmentProps) {
  const stats = [
    { label: 'Total recon runs', value: String(recon.totalRuns), sub: 'On selected date' },
    { label: 'Records processed', value: String(recon.cumulativeRecordsProcessed), sub: 'On selected date' },
    {
      label: 'AI contribution (latest)',
      value: recon.latestRun ? `${recon.latestRun.aiContributionPct}%` : '0%',
      sub: recon.latestRun?.label ?? 'No runs yet',
    },
    { label: 'Open cases', value: String(openCasesCount), sub: 'Unresolved', link: '/cases' },
    {
      label: 'Needs your decision',
      value: String(needsDecisionCount),
      sub: 'Human review',
      link: '/cases?filter=needs_decision',
    },
  ]

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {stats.map(({ label, value, sub, link }) => {
        const inner = (
          <>
            <p className="text-[11.5px] font-medium text-zinc-500">{label}</p>
            <p className="mt-1 text-[22px] font-semibold tracking-tight text-zinc-900">{value}</p>
            <p className="mt-0.5 text-[11.5px] text-zinc-400">{sub}</p>
          </>
        )

        return link ? (
          <Link
            key={label}
            to={link}
            className="rounded-2xl border border-zinc-200 bg-white p-4 transition-colors hover:border-blue-200 hover:shadow-sm"
          >
            {inner}
          </Link>
        ) : (
          <div key={label} className="rounded-2xl border border-zinc-200 bg-white p-4">
            {inner}
          </div>
        )
      })}
    </div>
  )
}
