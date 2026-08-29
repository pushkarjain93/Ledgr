import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { DEMO_MERCHANT } from '../lib/constants'
import { computeDashboardMetrics, listCases } from '../lib/dashboardMetrics'
import {
  dismissBatchNotification,
  hasPendingBatch,
  loadPersistedState,
  persistState,
  resetMerchantState,
  stateForSelectedDate,
  todayISO,
} from '../lib/merchantState'
import type { Case, MerchantSession, MerchantState } from '../types/case'

type AppContextValue = {
  merchant: MerchantSession | null
  state: MerchantState | null
  selectedDate: string
  setSelectedDate: (date: string) => void
  cases: Case[]
  dashboard: ReturnType<typeof computeDashboardMetrics> | null
  hasNewBatch: boolean
  dismissNotification: () => void
  resetDemoData: () => void
  login: (email: string, password: string) => boolean
  logout: () => void
}

const AppContext = createContext<AppContextValue | null>(null)

const SESSION_KEY = 'ledgr_session'

function loadSession(): MerchantSession | null {
  const raw = localStorage.getItem(SESSION_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as MerchantSession
  } catch {
    return null
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [merchant, setMerchant] = useState<MerchantSession | null>(() => loadSession())

  const [merchantState, setMerchantState] = useState<MerchantState | null>(() => {
    const m = loadSession()
    return m ? loadPersistedState(m.merchant_id) : null
  })

  const [selectedDate, setSelectedDate] = useState(todayISO)

  const login = useCallback((email: string, password: string) => {
    const normalized = email.trim().toLowerCase()
    if (
      normalized === DEMO_MERCHANT.email &&
      password.trim().toLowerCase() === 'demo123'
    ) {
      const session: MerchantSession = { ...DEMO_MERCHANT }
      localStorage.setItem(SESSION_KEY, JSON.stringify(session))
      setMerchant(session)
      const state = loadPersistedState(session.merchant_id)
      setMerchantState(state)
      return true
    }
    return false
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(SESSION_KEY)
    setMerchant(null)
    setMerchantState(null)
  }, [])

  const dismissNotification = useCallback(() => {
    if (!merchant || !merchantState) return
    const next = dismissBatchNotification(merchantState)
    setMerchantState(next)
    persistState(merchant.merchant_id, next)
  }, [merchant, merchantState])

  const resetDemoData = useCallback(() => {
    if (!merchant) return
    const fresh = resetMerchantState(merchant.merchant_id)
    setMerchantState(fresh)
    setSelectedDate(todayISO())
  }, [merchant])

  const dateFilteredState = useMemo(() => {
    if (!merchantState) return null
    return stateForSelectedDate(merchantState, selectedDate)
  }, [merchantState, selectedDate])

  const cases = useMemo(() => {
    if (!dateFilteredState) return []
    return listCases(dateFilteredState)
  }, [dateFilteredState])

  const dashboard = useMemo(
    () => (dateFilteredState ? computeDashboardMetrics(dateFilteredState) : null),
    [dateFilteredState],
  )

  const hasNewBatch = merchantState
    ? hasPendingBatch(merchantState) && !merchantState.notification_seen
    : false

  const value = useMemo(
    () => ({
      merchant,
      state: dateFilteredState,
      selectedDate,
      setSelectedDate,
      cases,
      dashboard,
      hasNewBatch,
      dismissNotification,
      resetDemoData,
      login,
      logout,
    }),
    [
      merchant,
      dateFilteredState,
      selectedDate,
      cases,
      dashboard,
      hasNewBatch,
      dismissNotification,
      resetDemoData,
      login,
      logout,
    ],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
