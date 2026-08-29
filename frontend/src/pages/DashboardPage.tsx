import { Link } from 'react-router-dom'
import { PageHeader } from '../components/layout/PageHeader'
import {
  ImprovementChart,
  ReconciliationChart,
} from '../components/dashboard/ReconciliationCharts'
import { StatsSegment } from '../components/dashboard/StatsSegment'
import { RecentActivity } from '../components/dashboard/RecentActivity'
import { useApp } from '../context/AppContext'
import { isUnresolved } from '../lib/caseUtils'
import { formatDisplayDate } from '../lib/merchantState'
import { computeReconciliationDashboard } from '../lib/reconciliationMetrics'

export function DashboardPage() {
  const { state, cases, dashboard, selectedDate, hasNewBatch } = useApp()

  if (!state || !dashboard) return null

  const recon = computeReconciliationDashboard(state.reconciliation_runs, true)
  const openCasesCount = cases.filter(isUnresolved).length
  const isEmpty = recon.totalRuns === 0

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader title="Dashboard" showWelcome />

      <div className="mx-auto w-full max-w-[1160px] flex-1 space-y-6 px-6 py-6 lg:px-8 lg:py-8">
        {/* Sync & Reconcile CTA */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-zinc-200 bg-white p-5">
          <div>
            <p className="text-[15px] font-medium text-zinc-900">
              {isEmpty ? 'No reconciliation yet' : `${recon.totalRuns} run(s) on this date`}
            </p>
            <p className="mt-0.5 text-[13px] text-zinc-500">
              {isEmpty
                ? 'Sync your sources and run your first reconciliation to populate the dashboard.'
                : `Showing activity for ${formatDisplayDate(selectedDate)}`}
            </p>
          </div>
          <Link
            to="/reconciliations"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-blue-700"
          >
            <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.5">
              <path d="M4 10h12M12 6l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Sync &amp; Reconcile
          </Link>
        </div>

        {hasNewBatch && (
          <button
            type="button"
            onClick={() => document.querySelector<HTMLButtonElement>('[aria-label="Notifications"]')?.click()}
            className="w-full rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-left text-[13px] text-amber-800 transition-colors hover:bg-amber-100"
          >
            <span className="font-medium">New batch waiting</span>
            {' — '}click the bell to reconcile or ignore
          </button>
        )}

        <StatsSegment
          recon={recon}
          needsDecisionCount={dashboard.needsDecisionCount}
          openCasesCount={openCasesCount}
        />

        <div className="grid gap-6 lg:grid-cols-2">
          <ReconciliationChart runs={recon.runs} />
          <ImprovementChart
            latest={recon.latestRun}
            previous={recon.previousRun}
            aiContributionDelta={recon.improvement.aiContributionDelta}
          />
        </div>

        <RecentActivity runs={recon.runs} />
      </div>
    </div>
  )
}
