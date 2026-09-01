import { Link } from 'react-router-dom'
import type { RunChartPoint } from '../../lib/reconciliationMetrics'

type RecentActivityProps = {
  runs: RunChartPoint[]
}

export function RecentActivity({ runs }: RecentActivityProps) {
  const recent = [...runs].reverse()

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
      <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-4 dark:border-zinc-800">
        <div>
          <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Recent activity</h2>
          <p className="mt-0.5 text-[12.5px] text-zinc-500 dark:text-zinc-400">Reconciliation run history</p>
        </div>
        <Link to="/reconciliations" className="text-[13px] font-medium text-zinc-600 hover:text-zinc-900 hover:underline dark:text-zinc-400 dark:hover:text-zinc-100">
          View all →
        </Link>
      </div>

      {recent.length === 0 ? (
        <p className="px-6 py-10 text-center text-[13px] text-zinc-400 dark:text-zinc-500">
          No activity on this date.
        </p>
      ) : (
        <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {recent.map((run) => (
            <li key={run.runId} className="px-6 py-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-[13.5px] font-medium text-zinc-900 dark:text-zinc-50">
                    Reconciliation completed · {run.label}
                  </p>
                  <p className="mt-0.5 text-[12.5px] text-zinc-500 dark:text-zinc-400">
                    {run.dateLabel} · {run.timeLabel}
                  </p>
                </div>
                <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                  Completed
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px] text-zinc-600 dark:text-zinc-300">
                <span><span className="text-zinc-400 dark:text-zinc-500">Processed </span><span className="font-medium">{run.totalRecords}</span></span>
                <span><span className="text-zinc-400 dark:text-zinc-500">Auto matched </span><span className="font-medium">{run.autoMatched}</span></span>
                <span><span className="text-zinc-400 dark:text-zinc-500">Needs review </span><span className="font-medium">{run.aiResolved + run.exceptions}</span></span>
                <span><span className="text-zinc-400 dark:text-zinc-500">Exceptions </span><span className="font-medium">{run.exceptions}</span></span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
