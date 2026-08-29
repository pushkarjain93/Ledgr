import type { ReconciliationRun } from '../types/case'

export type RunChartPoint = {
  runId: string
  batchId: number
  label: string
  dateLabel: string
  timeLabel: string
  totalRecords: number
  autoMatched: number
  aiResolved: number
  exceptions: number
  autoMatchRate: number
  aiContributionPct: number
  timestamp: string
}

export type ReconciliationDashboard = {
  runs: RunChartPoint[]
  totalRuns: number
  cumulativeRecordsProcessed: number
  latestRun: RunChartPoint | null
  previousRun: RunChartPoint | null
  improvement: {
    aiContributionDelta: number | null
  }
  hasUnreadNotification: boolean
}

function parseRun(run: ReconciliationRun): RunChartPoint {
  const total = run.total_records ?? 0
  const auto = run.auto_matched ?? 0
  const aiResolved = run.ai_resolved ?? 0
  const at = new Date(run.timestamp)

  return {
    runId: run.run_id,
    batchId: run.batch_id,
    label: `Batch ${run.batch_id}`,
    dateLabel: at.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }),
    timeLabel: at.toLocaleTimeString('en-IN', {
      hour: 'numeric',
      minute: '2-digit',
    }),
    totalRecords: total,
    autoMatched: auto,
    aiResolved,
    exceptions: run.exceptions ?? 0,
    autoMatchRate: total > 0 ? Math.round((auto / total) * 100) : 0,
    aiContributionPct: total > 0 ? Math.round((aiResolved / total) * 100) : 0,
    timestamp: run.timestamp,
  }
}

export function computeReconciliationDashboard(
  runs: ReconciliationRun[],
  notificationSeen: boolean,
): ReconciliationDashboard {
  const chronological = [...runs]
    .map(parseRun)
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))

  const latestRun = chronological.at(-1) ?? null
  const previousRun = chronological.length > 1 ? chronological.at(-2)! : null

  let aiContributionDelta: number | null = null
  if (latestRun && previousRun) {
    aiContributionDelta = latestRun.aiContributionPct - previousRun.aiContributionPct
  }

  return {
    runs: chronological,
    totalRuns: chronological.length,
    cumulativeRecordsProcessed: chronological.reduce((s, r) => s + r.totalRecords, 0),
    latestRun,
    previousRun,
    improvement: { aiContributionDelta },
    hasUnreadNotification: !notificationSeen,
  }
}
