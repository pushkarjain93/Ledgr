import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { AskAiPanel } from '../AskAiPanel'
import { playNotificationChime } from '../../lib/notificationSound'
import { shiftISODate, todayISO } from '../../lib/merchantState'
import { BellBatchPopover, BellEmptyPopover } from './NewBatchOverlay'

function BellIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-[18px] w-[18px]">
      <path d="M10 2.5a4.5 4.5 0 0 0-4.5 4.5v2.1L4 11.5h12l-1.5-2.4V7a4.5 4.5 0 0 0-4.5-4.5z" strokeLinejoin="round" />
      <path d="M8 14a2 2 0 0 0 4 0" strokeLinecap="round" />
    </svg>
  )
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-[18px] w-[18px]">
      <path d="M10 2.5v4M10 13.5v4M4.5 10h4M11.5 10h4M6.2 6.2l2.8 2.8M11 11l2.8 2.8M13.8 6.2 11 9M9 11l-2.8 2.8" strokeLinecap="round" />
    </svg>
  )
}

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      className={`h-[18px] w-[18px] ${spinning ? 'animate-spin' : ''}`}
    >
      <path d="M16.5 10a6.5 6.5 0 1 1-1.9-4.6" strokeLinecap="round" />
      <path d="M16.5 3.5V7H13" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ChevronIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4">
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0 text-zinc-400 dark:text-zinc-500">
      <rect x="3.5" y="4.5" width="13" height="12" rx="1.5" />
      <path d="M3.5 8h13M7 3v3M13 3v3" strokeLinecap="round" />
    </svg>
  )
}

function DateNavButton({
  label,
  onClick,
  disabled = false,
  children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 transition-colors hover:bg-zinc-50 hover:text-zinc-900 disabled:cursor-not-allowed disabled:border-zinc-100 disabled:bg-zinc-50 disabled:text-zinc-300 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50 dark:disabled:border-zinc-800 dark:disabled:bg-zinc-900/50 dark:disabled:text-zinc-600"
    >
      {children}
    </button>
  )
}

type PageHeaderProps = {
  title: string
  /** Dashboard-only: welcome block + date sit below the title/toolbar divider. */
  variant?: 'default' | 'dashboard'
  children?: ReactNode
}

export function PageHeader({ title, variant = 'default', children }: PageHeaderProps) {
  const {
    merchant,
    cases,
    logout,
    hasNewBatch,
    selectedDate,
    setSelectedDate,
    resetDemoData,
    refresh,
    aiInProgress,
  } = useApp()
  const navigate = useNavigate()
  const [profileOpen, setProfileOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [aiOpen, setAiOpen] = useState(false)
  const [bellMenuOpen, setBellMenuOpen] = useState(false)
  const [batchPopoverOpen, setBatchPopoverOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)
  const bellRef = useRef<HTMLDivElement>(null)

  const today = todayISO()
  const canGoNext = selectedDate < today

  // Auto-show the popover when new data lands; closing it only hides the panel.
  // The chime fires on the false -> true EDGE only, so it sounds once when data
  // actually arrives rather than on every re-render or navigation.
  const wasNotifying = useRef(false)
  useEffect(() => {
    if (hasNewBatch && !wasNotifying.current) {
      playNotificationChime()
    }
    wasNotifying.current = hasNewBatch
    setBatchPopoverOpen(hasNewBatch)
  }, [hasNewBatch])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (profileRef.current && !profileRef.current.contains(target)) {
        setProfileOpen(false)
      }
      if (bellRef.current && !bellRef.current.contains(target)) {
        setBellMenuOpen(false)
        setBatchPopoverOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function handleBellClick() {
    if (hasNewBatch) {
      setBatchPopoverOpen((v) => !v)
      return
    }
    setBellMenuOpen((v) => !v)
  }

  const initials = merchant?.company_name
    ?.split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  const bookmarkedCount = cases.filter((c) => c.bookmarked).length

  const investigating = aiInProgress > 0

  async function handleRefresh() {
    if (refreshing) return
    setRefreshing(true)
    try {
      await refresh()
    } finally {
      // Always spin for a beat. An instant snap gives no feedback that
      // anything happened when the counts have not moved yet.
      setTimeout(() => setRefreshing(false), 450)
    }
  }

  const toolbar = (
    <div className="flex items-center gap-2">
      {/* Manual refresh. Verdicts land in chunks over a couple of minutes and
          the app polls on its own, but a visible control means the user can
          pull the latest counts on demand instead of wondering whether the
          screen is stale. */}
      <button
        type="button"
        onClick={handleRefresh}
        disabled={refreshing}
        aria-label="Refresh reconciliation data"
        title={investigating ? `AI is investigating ${aiInProgress} case(s) — refresh for the latest` : 'Refresh'}
        className="relative flex h-9 items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 text-[13px] font-medium text-zinc-600 transition-colors hover:border-zinc-300 hover:text-zinc-900 disabled:opacity-60 dark:border-zinc-600 dark:text-zinc-300 dark:hover:border-zinc-500 dark:hover:text-zinc-50"
      >
        <RefreshIcon spinning={refreshing || investigating} />
        {investigating && (
          <span className="tabular-nums text-[12px] text-blue-600 dark:text-blue-400">
            {aiInProgress}
          </span>
        )}
      </button>
      <div className="relative" ref={bellRef}>
        <button
          type="button"
          className="relative flex h-9 w-9 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label="Notifications"
          aria-expanded={batchPopoverOpen || bellMenuOpen}
          onClick={handleBellClick}
        >
          <BellIcon />
          {hasNewBatch && (
            <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white dark:ring-zinc-900" />
          )}
        </button>

        {hasNewBatch && batchPopoverOpen && (
          <BellBatchPopover onClose={() => setBatchPopoverOpen(false)} />
        )}
        {bellMenuOpen && !hasNewBatch && (
          <BellEmptyPopover onClose={() => setBellMenuOpen(false)} />
        )}
      </div>

      <button
        type="button"
        className="flex h-9 items-center gap-1.5 rounded-lg border border-zinc-200 px-3 text-[13px] font-medium text-zinc-600 transition-colors hover:border-zinc-300 hover:text-zinc-900 dark:border-zinc-600 dark:text-zinc-300 dark:hover:border-zinc-500 dark:hover:text-zinc-50"
        onClick={() => setAiOpen((v) => !v)}
      >
        <SparkIcon />
        <span className="hidden sm:inline">AI assistant</span>
      </button>

      <div className="relative" ref={profileRef}>
        <button
          type="button"
          onClick={() => setProfileOpen((v) => !v)}
          className="flex h-9 items-center gap-2 rounded-lg border border-zinc-200 pl-1.5 pr-2.5 transition-colors hover:border-zinc-300 dark:border-zinc-600 dark:hover:border-zinc-500"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-100 text-[10px] font-semibold text-blue-700 dark:bg-blue-500/20 dark:text-blue-300">
            {initials ?? 'L'}
          </span>
          <ChevronIcon />
        </button>

        {profileOpen && (
          <div className="absolute right-0 z-20 mt-2 w-52 rounded-xl border border-zinc-200 bg-white py-1 shadow-lg dark:border-zinc-600 dark:bg-zinc-900 dark:shadow-black/40">
            <div className="border-b border-zinc-100 px-3 py-2.5 dark:border-zinc-700">
              <p className="truncate text-[13px] font-medium text-zinc-900 dark:text-zinc-50">
                {merchant?.company_name}
              </p>
              <p className="truncate text-[11.5px] text-zinc-500 dark:text-zinc-400">{merchant?.email}</p>
            </div>
            <Link
              to="/settings"
              className="block px-3 py-2 text-[13px] text-zinc-600 hover:bg-zinc-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
              onClick={() => setProfileOpen(false)}
            >
              Settings
            </Link>
            <Link
              to="/cases?filter=bookmarked"
              className="flex items-center justify-between px-3 py-2 text-[13px] text-zinc-600 hover:bg-zinc-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
              onClick={() => setProfileOpen(false)}
            >
              <span>Bookmarked cases</span>
              {bookmarkedCount > 0 && (
                <span className="rounded-md bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
                  {bookmarkedCount}
                </span>
              )}
            </Link>
            <button
              type="button"
              className="block w-full px-3 py-2 text-left text-[13px] text-zinc-600 hover:bg-zinc-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
              onClick={() => {
                setProfileOpen(false)
                resetDemoData()
              }}
            >
              Reset demo data
            </button>
            <button
              type="button"
              className="block w-full px-3 py-2 text-left text-[13px] text-red-600 hover:bg-zinc-50 dark:text-red-400 dark:hover:bg-zinc-800"
              onClick={() => {
                logout()
                navigate('/login')
              }}
            >
              Logout
            </button>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <>
      {/* Title row — white bg + bottom line only */}
      <header className="border-b border-zinc-200 bg-white px-6 py-3.5 dark:border-zinc-700 dark:bg-zinc-900 lg:px-8">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-[18px] font-semibold tracking-[-0.02em] text-zinc-900 dark:text-zinc-50">
            {title}
          </h1>
          {toolbar}
        </div>
      </header>

      {/* Dashboard welcome + date — same row, page bg (no white) */}
      {variant === 'dashboard' && (
        <div className="flex items-center justify-between gap-4 px-6 py-4 lg:px-8">
          <p className="text-[28px] font-semibold tracking-[-0.03em] text-zinc-900 dark:text-zinc-50 sm:text-[32px]">
            Welcome back! 👋
          </p>
          <div className="flex shrink-0 items-center gap-1.5">
            <DateNavButton
              label="Previous day"
              onClick={() => setSelectedDate(shiftISODate(selectedDate, -1))}
            >
              <span className="text-[15px] leading-none" aria-hidden>
                ←
              </span>
            </DateNavButton>
            <div className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 dark:border-zinc-600 dark:bg-zinc-900">
              <CalendarIcon />
              <label htmlFor="dashboard-date" className="sr-only">
                Filter by date
              </label>
              <input
                id="dashboard-date"
                type="date"
                value={selectedDate}
                max={today}
                onChange={(e) => {
                  const next = e.target.value
                  setSelectedDate(next > today ? today : next)
                }}
                className="border-0 bg-transparent text-[13px] text-zinc-800 outline-none focus:ring-0 dark:text-zinc-100"
              />
            </div>
            <DateNavButton
              label="Next day"
              disabled={!canGoNext}
              onClick={() => {
                if (canGoNext) setSelectedDate(shiftISODate(selectedDate, 1))
              }}
            >
              <span className="text-[15px] leading-none" aria-hidden>
                →
              </span>
            </DateNavButton>
          </div>
        </div>
      )}

      {aiOpen && (
        <div className="px-6 pb-3 lg:px-8">
          <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-600 dark:bg-zinc-900">
            <AskAiPanel compact />
          </div>
        </div>
      )}

      {children}
    </>
  )
}
