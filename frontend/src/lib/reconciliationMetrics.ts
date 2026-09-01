import type { ReconciliationRun } from '../types/case'
import {
  filterRunsByPeriod,
  monthRange,
  shiftISODate,
  type ReconciliationPeriod,
} from './merchantState'

export type RunChartPoint = {
  runId: string
  batchId: number
  label: string
  dateLabel: string
  timeLabel: string
  totalRecords: number
  autoMatched: number
  awaitingSettlement: number
  aiResolved: number
  exceptions: number
  autoMatchRate: number
  aiContributionPct: number
  manualWorkEliminationPct: number
  manualWorkRemainingPct: number
  manualReviewCount: number
  autoMatchedPct: number
  aiResolvedPct: number
  runNumber: number
  timestamp: string
}

export type ReconciliationGraphPoint = {
  id: string
  label: string
  subLabel?: string
  totalRecords: number
  autoMatched: number
  aiResolved: number
  manualReview: number
  runCount: number
  timestamp: string
}

function emptyGraphBucket(id: string, label: string, subLabel: string, timestamp: string): ReconciliationGraphPoint {
  return {
    id,
    label,
    subLabel,
    totalRecords: 0,
    autoMatched: 0,
    aiResolved: 0,
    manualReview: 0,
    runCount: 0,
    timestamp,
  }
}

function addRunToBucket(
  bucket: ReconciliationGraphPoint,
  run: ReconciliationRun,
): ReconciliationGraphPoint {
  const total = run.total_records ?? 0
  const auto = run.auto_matched ?? 0
  const ai = run.ai_resolved ?? 0
  return {
    ...bucket,
    totalRecords: bucket.totalRecords + total,
    autoMatched: bucket.autoMatched + auto,
    aiResolved: bucket.aiResolved + ai,
    manualReview: bucket.manualReview + Math.max(0, total - auto - ai),
    runCount: bucket.runCount + 1,
  }
}

export function buildReconciliationGraphSeries(
  runs: ReconciliationRun[],
  period: ReconciliationPeriod,
  referenceDate: string,
): ReconciliationGraphPoint[] {
  const filtered = filterRunsByPeriod(runs, period, referenceDate)

  if (period === 'day') {
    return filtered
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
      .map((run, index) => {
        const at = new Date(run.timestamp)
        const total = run.total_records ?? 0
        const auto = run.auto_matched ?? 0
        const ai = run.ai_resolved ?? 0
        return {
          id: run.run_id,
          label: at.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' }),
          subLabel: `Run ${index + 1}`,
          totalRecords: total,
          autoMatched: auto,
          aiResolved: ai,
          manualReview: Math.max(0, total - auto - ai),
          runCount: 1,
          timestamp: run.timestamp,
        }
      })
  }

  if (period === 'month') {
    const { start, end } = monthRange(referenceDate)
    const buckets = new Map<string, ReconciliationGraphPoint>()

    for (let day = start; day <= end; day = shiftISODate(day, 1)) {
      const at = new Date(`${day}T12:00:00`)
      buckets.set(
        day,
        emptyGraphBucket(
          day,
          String(at.getDate()),
          at.toLocaleDateString('en-IN', { weekday: 'short' }),
          `${day}T12:00:00`,
        ),
      )
    }

    for (const run of filtered) {
      const day = run.timestamp.slice(0, 10)
      const bucket = buckets.get(day)
      if (bucket) buckets.set(day, addRunToBucket(bucket, run))
    }

    return [...buckets.values()]
  }

  const year = referenceDate.slice(0, 4)
  const buckets = new Map<string, ReconciliationGraphPoint>()

  for (let month = 0; month < 12; month += 1) {
    const at = new Date(Number(year), month, 1, 12)
    const monthKey = `${year}-${String(month + 1).padStart(2, '0')}`
    buckets.set(
      monthKey,
      emptyGraphBucket(
        monthKey,
        at.toLocaleDateString('en-IN', { month: 'short' }),
        at.toLocaleDateString('en-IN', { month: 'long' }),
        `${monthKey}-01T12:00:00`,
      ),
    )
  }

  for (const run of filtered) {
    const monthKey = run.timestamp.slice(0, 7)
    const bucket = buckets.get(monthKey)
    if (bucket) buckets.set(monthKey, addRunToBucket(bucket, run))
  }

  return [...buckets.values()]
}

export type ReconciliationDashboard = {
  runs: RunChartPoint[]
  totalRuns: number
  cumulativeRecordsProcessed: number
  latestRun: RunChartPoint | null
  hasUnreadNotification: boolean
}

function pctOf(part: number, total: number): number {
  if (total <= 0) return 0
  return Math.round((part / total) * 100)
}

export function parseRun(run: ReconciliationRun, runNumber: number): RunChartPoint {
  const total = run.total_records ?? 0
  const auto = run.auto_matched ?? 0
  const awaiting = run.awaiting_settlement ?? 0
  const aiResolved = run.ai_resolved ?? 0
  const exceptions = run.exceptions ?? 0
  // MANUAL WORK ELIMINATED = (auto matched + AI handled) / records that
  // actually needed reconciling.
  //
  // Both halves matter:
  //  * auto matched needed no human at all;
  //  * an AI-handled record still ends with a human decision, but the
  //    investigation -- pulling the settlement, comparing the fee band,
  //    writing the finding -- was done for them. That is eliminated work.
  //  * COD still inside its collection window is EXCLUDED FROM THE
  //    DENOMINATOR, not counted as eliminated. No money has arrived yet, so
  //    there is no reconciliation work to eliminate; leaving it in the
  //    denominator understated the result by penalising the tool for orders
  //    it has not been asked to do anything about yet.
  const eliminated = auto + aiResolved
  const reconcilable = Math.max(0, total - awaiting)
  const manualReview = Math.max(0, reconcilable - eliminated)
  const at = new Date(run.timestamp)

  return {
    runId: run.run_id,
    batchId: run.batch_id,
    label: `Run ${runNumber}`,
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
    awaitingSettlement: awaiting,
    aiResolved,
    exceptions,
    autoMatchRate: pctOf(auto, reconcilable),
    aiContributionPct: pctOf(aiResolved, reconcilable),
    manualWorkEliminationPct: pctOf(eliminated, reconcilable),
    manualWorkRemainingPct: pctOf(manualReview, reconcilable),
    manualReviewCount: manualReview,
    autoMatchedPct: pctOf(auto, reconcilable),
    aiResolvedPct: pctOf(aiResolved, reconcilable),
    runNumber,
    timestamp: run.timestamp,
  }
}

export function computeReconciliationDashboard(
  runs: ReconciliationRun[],
  notificationSeen: boolean,
): ReconciliationDashboard {
  const chronological = [...runs]
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    .map((run, index) => parseRun(run, index + 1))

  const latestRun = chronological.at(-1) ?? null

  return {
    runs: chronological,
    totalRuns: chronological.length,
    cumulativeRecordsProcessed: chronological.reduce((s, r) => s + r.totalRecords, 0),
    latestRun,
    hasUnreadNotification: !notificationSeen,
  }
}
