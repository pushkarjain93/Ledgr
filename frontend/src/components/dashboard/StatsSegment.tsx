import { Link } from 'react-router-dom'
import type { ReconciliationDashboard } from '../../lib/reconciliationMetrics'
import { scrollAppMainToTop } from '../../lib/scrollAppMain'

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
      label: 'Manual work eliminated',
      value: recon.latestRun ? `${recon.latestRun.manualWorkEliminationPct}%` : '0%',
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

  // ONE surface class for both variants. They used to be written out twice and
  // drifted: the plain <div> never got the dark: overrides, so in dark mode
  // three cards stayed white while the two linked ones went dark.
  const cardBase =
    'rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900'

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {stats.map(({ label, value, sub, link }) => {
        const inner = (
          <>
            <p className="text-[11.5px] font-medium text-zinc-500 dark:text-zinc-400">{label}</p>
            {/* Without the dark override this was zinc-900 on a zinc-900 card —
                the number rendered black-on-black and read as missing data. */}
            <p className="mt-1 text-[22px] font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
              {value}
            </p>
            <p className="mt-0.5 text-[11.5px] text-zinc-400 dark:text-zinc-500">{sub}</p>
          </>
        )

        return link ? (
          <Link
            key={label}
            to={link}
            onClick={scrollAppMainToTop}
            className={`${cardBase} transition-colors hover:border-zinc-300 hover:shadow-sm dark:hover:border-zinc-600`}
          >
            {inner}
          </Link>
        ) : (
          <div key={label} className={cardBase}>
            {inner}
          </div>
        )
      })}
    </div>
  )
}
