import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { formatDisplayDate } from '../../lib/merchantState'
import { NewBatchOverlay } from './NewBatchOverlay'

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

function ChevronIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4">
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

type PageHeaderProps = {
  title: string
  showWelcome?: boolean
  children?: ReactNode
}

export function PageHeader({ title, showWelcome = false, children }: PageHeaderProps) {
  const {
    merchant,
    logout,
    hasNewBatch,
    selectedDate,
    setSelectedDate,
    resetDemoData,
  } = useApp()
  const navigate = useNavigate()
  const [profileOpen, setProfileOpen] = useState(false)
  const [aiOpen, setAiOpen] = useState(false)
  const [bellOpen, setBellOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const initials = merchant?.company_name
    ?.split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <>
      <header className="border-b border-zinc-200 bg-white px-6 py-4 lg:px-8">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-[18px] font-semibold tracking-[-0.02em] text-zinc-900">{title}</h1>

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="relative flex h-9 w-9 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-800"
              aria-label="Notifications"
              onClick={() => setBellOpen(true)}
            >
              <BellIcon />
              {hasNewBatch && (
                <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white" />
              )}
            </button>

            <button
              type="button"
              className="flex h-9 items-center gap-1.5 rounded-lg border border-zinc-200 px-3 text-[13px] font-medium text-zinc-600 transition-colors hover:border-zinc-300 hover:text-zinc-900"
              onClick={() => setAiOpen((v) => !v)}
            >
              <SparkIcon />
              <span className="hidden sm:inline">AI assistant</span>
            </button>

            <div className="relative" ref={profileRef}>
              <button
                type="button"
                onClick={() => setProfileOpen((v) => !v)}
                className="flex h-9 items-center gap-2 rounded-lg border border-zinc-200 pl-1.5 pr-2.5 transition-colors hover:border-zinc-300"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-100 text-[10px] font-semibold text-blue-700">
                  {initials ?? 'L'}
                </span>
                <ChevronIcon />
              </button>

              {profileOpen && (
                <div className="absolute right-0 z-20 mt-2 w-52 rounded-xl border border-zinc-200 bg-white py-1 shadow-lg">
                  <div className="border-b border-zinc-100 px-3 py-2.5">
                    <p className="truncate text-[13px] font-medium text-zinc-900">
                      {merchant?.company_name}
                    </p>
                    <p className="truncate text-[11.5px] text-zinc-500">{merchant?.email}</p>
                  </div>
                  <Link
                    to="/settings"
                    className="block px-3 py-2 text-[13px] text-zinc-600 hover:bg-zinc-50"
                    onClick={() => setProfileOpen(false)}
                  >
                    Settings
                  </Link>
                  <button
                    type="button"
                    className="block w-full px-3 py-2 text-left text-[13px] text-zinc-600 hover:bg-zinc-50"
                    onClick={() => {
                      setProfileOpen(false)
                      resetDemoData()
                    }}
                  >
                    Reset demo data
                  </button>
                  <button
                    type="button"
                    className="block w-full px-3 py-2 text-left text-[13px] text-red-600 hover:bg-zinc-50"
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
        </div>

        {showWelcome && (
          <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
            <p className="text-[15px] text-zinc-600">
              Welcome back
              {merchant?.company_name ? `, ${merchant.company_name.split(' ')[0]}` : ''}
            </p>
            <div className="flex flex-col items-end gap-0.5">
              <label htmlFor="dashboard-date" className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">
                Viewing data for
              </label>
              <input
                id="dashboard-date"
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-[13px] text-zinc-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              />
              <p className="text-[12px] text-zinc-400">{formatDisplayDate(selectedDate)}</p>
            </div>
          </div>
        )}

        {aiOpen && (
          <div className="mt-3 rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-[13px] text-zinc-500">
            AI assistant opens from case tickets and the review queue. Full chat coming soon.
          </div>
        )}

        {children}
      </header>

      <NewBatchOverlay open={bellOpen} hasBatch={hasNewBatch} onClose={() => setBellOpen(false)} />
    </>
  )
}
