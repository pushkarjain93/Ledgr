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
