import type { TransactionRecord } from './api'
import type { Case, ReconciliationRun } from '../types/case'

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

/**
 * Distinct records the engine has produced a verdict for.
 *
 * NOT the sum of each run's total_records: a run re-includes still-open orders
 * from earlier batches, so summing runs double-counts them (123 instead of
 * 112 on the two-batch demo) and made the dashboard disagree with every other
 * screen.
 *
 * = every order processed, plus the settlement-side records that raised a case
 * of their own (orphan bank credits, identified by a null order_id). Those are
 * real reconciled records that were never in the order count.
 */
export function totalReconciledRecords(cases: Case[], ordersProcessed: number): number {
  return ordersProcessed + cases.filter((c) => !c.order_id).length
}

export function buildReconciliationViewModel(
  runs: ReconciliationRun[],
  records: TransactionRecord[],
  cases: Case[] = [],
  ordersProcessed = 0,
): ReconciliationViewModel {
  // Money comes from the DE-DUPLICATED record set, not from summing runs.
  // A run re-includes still-open orders from earlier batches, so summing
  // run.expected_paise counted those orders twice -- Reconciliations showed
  // Rs 3,65,137.16 expected while Reports showed Rs 3,28,142.70 for the same
  // ledger. Only order-side rows carry an order's expected/received; the
  // settlement feed rows would double-count the money again.
  const orderRecords = records.filter((r) => r.record_kind === 'order')
  const expectedPaise = sumField(orderRecords, (r) => r.expected)
  const receivedPaise = sumField(orderRecords, (r) => r.received)
  const totals: RunTotals = {
    ...cumulativeTotals(runs),
    expectedPaise,
    receivedPaise,
    differencePaise: expectedPaise - receivedPaise,
  }
  const overpaidRecords = records.filter(isOverpaidRecord)
  const atRiskRecords = records.filter(isAtRiskRecord)
  const aiReviewCount = totals.aiResolved + totals.exceptions
  const total = totals.totalRecords || 1

  const pct = (n: number) => Math.round((n / total) * 1000) / 10

  // Outcome is built over CUMULATIVE ORDER RECORDS, partitioned by what
  // actually happened to each one. Every order lands in exactly one bucket and
  // they sum to `ordersProcessed` by construction, so this panel can never
  // disagree with the case queue beneath it.
  //
  // `ordersProcessed` is the de-duplicated ledger from the backend, NOT the
  // sum of each run's record count -- a run re-includes still-open orders from
  // earlier batches, so summing runs double-counts them.
  const open = cases.filter((c) => !c.resolution?.resolved)
  const byStatus = (...s: string[]) =>
    open.filter((c) => s.includes(c.case_status)).length
  const awaiting = byStatus('pending_settlement')
  const aiRecommendation = byStatus('manual_review', 'ai_recommendation')
  const investigating = byStatus('needs_ai', 'ai_pending')
  const needsInvestigation = byStatus('exception')

  // Orders that reconciled cleanly = every order processed, minus the ones
  // that raised a case.
  //
  // Subtract only ORDER-SIDE cases. `ordersProcessed` counts orders; a case
  // raised on the settlement side (an orphan bank credit, identified by a null
  // order_id) was never in that total, so subtracting it would under-count
  // clean orders. An earlier version subtracted cases.length and added the
  // resolved count back, which balanced ONLY because this dataset happens to
  // have as many settlement-side cases as resolved ones — a coincidence that
  // breaks the moment anyone resolves a case by hand.
  const orderSideCases = cases.filter((c) => c.order_id).length
  const cleanOrders = Math.max(ordersProcessed - orderSideCases, 0)
  // An auto-resolved case (bulk remittance proved payment) also needed no
  // human, so it belongs with the automatically settled records.
  const autoSettled = cleanOrders + cases.filter((c) => c.resolution?.resolved).length

  // Denominator must be what the segments actually sum to, not the order
  // count -- settlement-side cases are segments too, so dividing by orders
  // alone made the percentages add up to more than 100.
  const outcomeTotal = totalReconciledRecords(cases, ordersProcessed) || 1
  const opct = (n: number) => Math.round((n / outcomeTotal) * 1000) / 10

  const outcome: OutcomeSegment[] = [
    { key: 'auto', label: 'Auto matched', count: autoSettled, pct: opct(autoSettled), color: '#22c55e' },
    { key: 'awaiting', label: 'Awaiting settlement', count: awaiting, pct: opct(awaiting), color: '#a1a1aa' },
    { key: 'ai', label: 'AI recommendation', count: aiRecommendation, pct: opct(aiRecommendation), color: '#3b82f6' },
    { key: 'exc', label: 'Needs investigation', count: needsInvestigation, pct: opct(needsInvestigation), color: '#f97316' },
    // Transient: only non-zero while a batch is still being investigated.
    ...(investigating > 0
      ? [{ key: 'inv', label: 'Being investigated', count: investigating, pct: opct(investigating), color: '#8b5cf6' }]
      : []),
  ]

  return {
    totals,
    // Count by RECORD KIND. `received > 0` also matches order rows that were
    // paid, which reported 178 "settlements" against an 87-row feed.
    orderCount: orderRecords.length,
    settlementCount: records.filter((r) => r.record_kind === 'settlement').length,
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
