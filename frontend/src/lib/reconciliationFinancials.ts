import type { TransactionRecord } from './api'
import type { ReconciliationRun } from '../types/case'

export type RunTotals = {
  expectedPaise: number
  receivedPaise: number
  differencePaise: number
  totalRecords: number
  autoMatched: number
  aiResolved: number
  exceptions: number
}

export type RiskSummary = {
  amountPaise: number
  recordCount: number
}

export type OutcomeSegment = {
  key: string
  label: string
  count: number
  pct: number
  color: string
}

export type ReconciliationViewModel = {
  totals: RunTotals
  orderCount: number
  settlementCount: number
  overpaid: RiskSummary
  atRisk: RiskSummary
  aiReviewCount: number
  aiResolvedPct: number
  exceptionsPct: number
  outcome: OutcomeSegment[]
}

function isOverpaidRecord(r: TransactionRecord): boolean {
  return Boolean(r.matched_settlement) && r.delta > 0 && r.amount_at_risk > 0
}

function isAtRiskRecord(r: TransactionRecord): boolean {
  return Boolean(r.matched_settlement) && r.delta < 0 && r.amount_at_risk > 0
}

function sumField(records: TransactionRecord[], pick: (r: TransactionRecord) => number): number {
  return records.reduce((s, r) => s + pick(r), 0)
}

export function totalsFromRun(run: ReconciliationRun): RunTotals {
  const expectedPaise = run.expected_paise ?? 0
  const receivedPaise = run.received_paise ?? 0
  return {
    expectedPaise,
    receivedPaise,
    differencePaise: expectedPaise - receivedPaise,
    totalRecords: run.total_records ?? 0,
    autoMatched: run.auto_matched ?? 0,
    aiResolved: run.ai_resolved ?? 0,
    exceptions: run.exceptions ?? 0,
  }
}

export function cumulativeTotals(runs: ReconciliationRun[]): RunTotals {
  if (runs.length === 0) {
    return {
      expectedPaise: 0,
      receivedPaise: 0,
      differencePaise: 0,
      totalRecords: 0,
      autoMatched: 0,
      aiResolved: 0,
      exceptions: 0,
    }
  }
  return runs.reduce(
    (acc, run) => {
      const t = totalsFromRun(run)
      return {
        expectedPaise: acc.expectedPaise + t.expectedPaise,
        receivedPaise: acc.receivedPaise + t.receivedPaise,
        differencePaise: acc.differencePaise + t.differencePaise,
        totalRecords: acc.totalRecords + t.totalRecords,
        autoMatched: acc.autoMatched + t.autoMatched,
        aiResolved: acc.aiResolved + t.aiResolved,
        exceptions: acc.exceptions + t.exceptions,
      }
    },
    {
      expectedPaise: 0,
      receivedPaise: 0,
      differencePaise: 0,
      totalRecords: 0,
      autoMatched: 0,
      aiResolved: 0,
      exceptions: 0,
    },
  )
}

function riskFromRecords(records: TransactionRecord[]): RiskSummary {
  return {
    amountPaise: sumField(records, (r) => r.amount_at_risk),
    recordCount: records.length,
  }
}

export function buildReconciliationViewModel(
  runs: ReconciliationRun[],
  records: TransactionRecord[],
): ReconciliationViewModel {
  const totals = cumulativeTotals(runs)
  const overpaidRecords = records.filter(isOverpaidRecord)
  const atRiskRecords = records.filter(isAtRiskRecord)
  const aiReviewCount = totals.aiResolved + totals.exceptions
  const total = totals.totalRecords || 1

  const pct = (n: number) => Math.round((n / total) * 1000) / 10

  const outcome: OutcomeSegment[] = [
    { key: 'auto', label: 'Auto Matched', count: totals.autoMatched, pct: pct(totals.autoMatched), color: '#22c55e' },
    { key: 'ai', label: 'AI Resolved', count: totals.aiResolved, pct: pct(totals.aiResolved), color: '#3b82f6' },
    { key: 'exc', label: 'Exceptions', count: totals.exceptions, pct: pct(totals.exceptions), color: '#f97316' },
  ]

  return {
    totals,
    orderCount: records.filter((r) => r.expected > 0).length,
    settlementCount: records.filter((r) => r.received > 0).length,
    overpaid: riskFromRecords(overpaidRecords),
    atRisk: riskFromRecords(atRiskRecords),
    aiReviewCount,
    aiResolvedPct: pct(totals.aiResolved),
    exceptionsPct: pct(totals.exceptions),
    outcome,
  }
}

export function barWidth(value: number, max: number): number {
  if (max <= 0) return 0
  return Math.min(100, Math.round((value / max) * 100))
}
