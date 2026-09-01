import type { MerchantState } from '../types/case'
import { TOTAL_BATCHES } from './constants'

const STATE_STORAGE_PREFIX = 'ledgr_merchant_state_'

export function createEmptyMerchantState(): MerchantState {
  return {
    current_batch: 1,
    processed_record_ids: [],
    reconciliation_runs: [],
    next_batch_available_at: null,
    notification_batch: 1,
    notification_created: true,
    notification_seen: false,
    cases: {},
    orders_processed: 0,
  }
}

export function loadPersistedState(merchantId: string): MerchantState {
  const raw = localStorage.getItem(`${STATE_STORAGE_PREFIX}${merchantId}`)
  if (!raw) return createEmptyMerchantState()
  try {
    return JSON.parse(raw) as MerchantState
  } catch {
    return createEmptyMerchantState()
  }
}

export function persistState(merchantId: string, state: MerchantState) {
  localStorage.setItem(`${STATE_STORAGE_PREFIX}${merchantId}`, JSON.stringify(state))
}

export function resetMerchantState(merchantId: string): MerchantState {
  const fresh = createEmptyMerchantState()
  persistState(merchantId, fresh)
  return fresh
}

export function todayISO(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Add or subtract days from an ISO date string (YYYY-MM-DD). */
export function shiftISODate(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T12:00:00`)
  d.setDate(d.getDate() + days)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function formatDisplayDate(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00`)
  return d.toLocaleDateString('en-IN', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export function filterRunsByDate(
  runs: MerchantState['reconciliation_runs'],
  selectedDate: string,
) {
  return runs.filter((r) => r.timestamp.slice(0, 10) === selectedDate)
}

export type ReconciliationPeriod = 'day' | 'month' | 'year'

function toISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function monthRange(isoDate: string): { start: string; end: string } {
  const d = new Date(`${isoDate}T12:00:00`)
  const y = d.getFullYear()
  const m = d.getMonth()
  const start = toISODate(new Date(y, m, 1))
  const end = toISODate(new Date(y, m + 1, 0))
  return { start, end }
}

export function yearRange(isoDate: string): { start: string; end: string } {
  const year = new Date(`${isoDate}T12:00:00`).getFullYear()
  return {
    start: `${year}-01-01`,
    end: `${year}-12-31`,
  }
}

export function filterRunsByPeriod(
  runs: MerchantState['reconciliation_runs'],
  period: ReconciliationPeriod,
  referenceDate: string,
): MerchantState['reconciliation_runs'] {
  if (period === 'day') {
    return filterRunsByDate(runs, referenceDate)
  }

  if (period === 'month') {
    const { start, end } = monthRange(referenceDate)
    return runs.filter((r) => {
      const day = r.timestamp.slice(0, 10)
      return day >= start && day <= end
    })
  }

  const year = referenceDate.slice(0, 4)
  return runs.filter((r) => r.timestamp.slice(0, 4) === year)
}

export function periodLabel(period: ReconciliationPeriod, referenceDate: string): string {
  if (period === 'day') {
    return formatDisplayDate(referenceDate)
  }
  if (period === 'month') {
    return new Date(`${referenceDate}T12:00:00`).toLocaleDateString('en-IN', {
      month: 'long',
      year: 'numeric',
    })
  }
  return referenceDate.slice(0, 4)
}

export function hasPendingBatch(state: MerchantState): boolean {
  return state.current_batch <= TOTAL_BATCHES && state.notification_created
}

export function dismissBatchNotification(state: MerchantState): MerchantState {
  return { ...state, notification_seen: true }
}

export function stateForSelectedDate(
  state: MerchantState,
  selectedDate: string,
): MerchantState {
  return {
    ...state,
    reconciliation_runs: filterRunsByDate(state.reconciliation_runs, selectedDate),
  }
}
