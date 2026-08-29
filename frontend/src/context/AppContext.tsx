import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, ApiError, getToken } from '../lib/api'
import { computeDashboardMetrics, listCases } from '../lib/dashboardMetrics'
import {
  hasPendingBatch,
  stateForSelectedDate,
  todayISO,
} from '../lib/merchantState'
import type { Case, MerchantSession, MerchantState } from '../types/case'

/**
 * Server state, sourced from the Ledgr API (../../api.py).
 *
 * The context surface is intentionally unchanged from the original
 * localStorage version — same fields, same names — so every screen keeps
 * working as written. Only where the data COMES FROM changed: the backend
 * now owns the case store, reconciliation runs, and batch scheduling.
 *
 * Financial state is deliberately not cached in localStorage. A stale local
 * copy of money figures is worse than a brief loading state. Only the auth
 * token persists locally.
 */
type AppContextValue = {
  merchant: MerchantSession | null
  state: MerchantState | null
  selectedDate: string
  setSelectedDate: (date: string) => void
  cases: Case[]
  dashboard: ReturnType<typeof computeDashboardMetrics> | null
  hasNewBatch: boolean
  /** Refetch server state — call after any mutation (reconcile, resolve…). */
  refresh: () => Promise<void>
  dismissNotification: () => void
  resetDemoData: () => Promise<void>
  login: (email: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  loading: boolean
  error: string | null
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [merchant, setMerchant] = useState<MerchantSession | null>(null)
  const [merchantState, setMerchantState] = useState<MerchantState | null>(null)
  const [selectedDate, setSelectedDate] = useState(todayISO)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Which batch the user has dismissed the bell for. Tracked per-batch (not
  // a plain boolean) so dismissing batch 1 doesn't also silence batch 2 when
  // it arrives later.
  const [dismissedBatch, setDismissedBatch] = useState<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const s = await api.getState()
      // Map the API response onto the MerchantState shape the UI already
      // expects. notification_created is derived rather than stored: the
      // server's own rule is that a batch beyond the first, currently
      // available, IS the "new data arrived" event.
      setMerchantState({
        current_batch: s.current_batch,
        processed_record_ids: [],
        reconciliation_runs: s.reconciliation_runs,
        next_batch_available_at: s.next_batch_available_at,
        notification_batch: s.notification_batch,
        // Any available, unreconciled batch is a bell event -- including the
        // very first one, so the app opens with data already waiting rather
        // than an empty screen and nothing to click.
        notification_created: s.batch_available,
        notification_seen: s.notification_seen,
        cases: s.cases,
      })
      setError(null)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setMerchant(null)
        setMerchantState(null)
        return
      }
      setError(err instanceof Error ? err.message : 'Something went wrong')
    }
  }, [])

  // Restore an existing session on load. A stored token proves nothing by
  // itself — the server validates it before any data is shown.
  useEffect(() => {
    let cancelled = false
    async function restore() {
      if (!getToken()) {
        setLoading(false)
        return
      }
      try {
        const { merchant: m } = await api.me()
        if (cancelled) return
        setMerchant(m)
        await refresh()
      } catch {
        if (!cancelled) setMerchant(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    restore()
    return () => {
      cancelled = true
    }
  }, [refresh])

  const login = useCallback(
    async (email: string, password: string) => {
      try {
        const m = await api.login(email, password)
        setMerchant(m)
        setDismissedBatch(null)
        await refresh()
        return true
      } catch {
        return false
      }
    },
    [refresh],
  )

  const logout = useCallback(async () => {
    await api.logout()
    setMerchant(null)
    setMerchantState(null)
  }, [])

  const dismissNotification = useCallback(
    () => setDismissedBatch(merchantState?.current_batch ?? null),
    [merchantState?.current_batch],
  )

  const resetDemoData = useCallback(async () => {
    await api.reset()
    setDismissedBatch(null)
    setSelectedDate(todayISO())
    await refresh()
  }, [refresh])

  const dateFilteredState = useMemo(() => {
    if (!merchantState) return null
    return stateForSelectedDate(merchantState, selectedDate)
  }, [merchantState, selectedDate])

  const cases = useMemo(
    () => (dateFilteredState ? listCases(dateFilteredState) : []),
    [dateFilteredState],
  )

  const dashboard = useMemo(
    () => (dateFilteredState ? computeDashboardMetrics(dateFilteredState) : null),
    [dateFilteredState],
  )

  // The bell rings whenever a real batch is sitting there unreconciled and
  // the user hasn't dismissed THAT batch. Reconciling it clears the bell on
  // its own (the batch stops being available), and the next batch re-rings it
  // once its timer passes.
  const hasNewBatch = merchantState
    ? hasPendingBatch(merchantState) && dismissedBatch !== merchantState.current_batch
    : false

  // A scheduled batch unlocks on a persisted server timestamp. Poll only
  // while one is genuinely pending; stop the moment it lands. No permanent
  // background timer.
  useEffect(() => {
    if (!merchantState?.next_batch_available_at) return
    const target = new Date(merchantState.next_batch_available_at).getTime()
    if (Date.now() >= target) return
    const id = window.setInterval(() => {
      if (Date.now() >= target) refresh()
    }, 5000)
    return () => window.clearInterval(id)
  }, [merchantState?.next_batch_available_at, refresh])

  const value = useMemo(
    () => ({
      merchant,
      state: dateFilteredState,
      selectedDate,
      setSelectedDate,
      cases,
      dashboard,
      hasNewBatch,
      refresh,
      dismissNotification,
      resetDemoData,
      login,
      logout,
      loading,
      error,
    }),
    [merchant, dateFilteredState, selectedDate, cases, dashboard, hasNewBatch,
     refresh, dismissNotification, resetDemoData, login, logout, loading, error],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
