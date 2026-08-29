import { Link } from 'react-router-dom'
import type { ReconciliationRun } from '../../types/case'
import { parseRun } from '../../lib/reconciliationMetrics'
import { scrollAppMainToTop } from '../../lib/scrollAppMain'

type RunHistoryTableProps = {
  runs: ReconciliationRun[]
}

export function RunHistoryTable({ runs }: RunHistoryTableProps) {
  const rows = [...runs]
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    .map((run, index) => parseRun(run, index + 1))
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp))

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
      <div className="border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Run history</h2>
        <p className="mt-0.5 text-[12.5px] text-zinc-500 dark:text-zinc-400">
          All completed reconciliation runs for this merchant
        </p>
      </div>

      {rows.length === 0 ? (
        <p className="px-5 py-12 text-center text-[13px] text-zinc-400 dark:text-zinc-500">
          No runs yet — sync when new data arrives.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-zinc-100 text-[11px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
                <th className="px-5 py-3">Run</th>
                <th className="px-5 py-3">Completed</th>
                <th className="px-5 py-3">Processed</th>
                <th className="px-5 py-3">Auto matched</th>
                <th className="px-5 py-3">AI resolved</th>
                <th className="px-5 py-3">Exceptions</th>
                <th className="px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {rows.map((run) => (
                <tr key={run.runId} className="text-zinc-700 dark:text-zinc-300">
                  <td className="px-5 py-3.5 font-medium text-zinc-900 dark:text-zinc-50">
                    Run {run.runNumber}
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap">
                    {run.dateLabel}
                    <span className="text-zinc-400 dark:text-zinc-500"> · {run.timeLabel}</span>
                  </td>
                  <td className="px-5 py-3.5 tabular-nums">{run.totalRecords}</td>
                  <td className="px-5 py-3.5 tabular-nums">{run.autoMatched}</td>
                  <td className="px-5 py-3.5 tabular-nums">{run.aiResolved}</td>
                  <td className="px-5 py-3.5 tabular-nums">{run.exceptions}</td>
                  <td className="px-5 py-3.5">
                    <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                      Completed
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows.length > 0 && (
        <div className="border-t border-zinc-100 px-5 py-3 dark:border-zinc-800">
          <Link
            to="/cases"
            onClick={scrollAppMainToTop}
            className="text-[13px] font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            Review open cases →
          </Link>
        </div>
      )}
    </section>
  )
}
