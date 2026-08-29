import { useEffect, useState, type ReactNode } from 'react'
import { useTheme, type Theme } from '../context/ThemeContext'
import { api, ApiError, type Sources } from '../lib/api'
import { useApp } from '../context/AppContext'
import {
  formatLastSync,
  sourceConnectionLabel,
  SOURCE_ROWS,
} from '../lib/sourceStatus'

type SectionId = 'sources' | 'security' | 'theme' | 'feedback'

const SECTIONS: { id: SectionId; title: string }[] = [
  { id: 'sources', title: 'Data sources' },
  { id: 'security', title: 'Security' },
  { id: 'theme', title: 'Theme' },
  { id: 'feedback', title: 'Send feedback' },
]

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className={`h-4 w-4 shrink-0 text-zinc-400 transition-transform duration-200 dark:text-zinc-500 ${open ? 'rotate-180' : ''}`}
      aria-hidden
    >
      <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SettingsRow({
  id,
  title,
  open,
  onToggle,
  children,
}: {
  id: SectionId
  title: string
  open: boolean
  onToggle: (id: SectionId) => void
  children: ReactNode
}) {
  const panelId = `settings-panel-${id}`
  const headerId = `settings-header-${id}`

  return (
    <>
      <button
        type="button"
        id={headerId}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => onToggle(id)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
      >
        <h2 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-50">{title}</h2>
        <Chevron open={open} />
      </button>
      {open && (
        <div
          id={panelId}
          role="region"
          aria-labelledby={headerId}
          className="border-t border-zinc-100 bg-zinc-50/80 px-5 py-4 dark:border-zinc-800 dark:bg-zinc-950/40"
        >
          {children}
        </div>
      )}
    </>
  )
}

function StatusDot({ tone }: { tone: ReturnType<typeof sourceConnectionLabel>['tone'] }) {
  const colors = {
    connected: 'bg-emerald-500',
    demo: 'bg-amber-400',
    error: 'bg-red-500',
    neutral: 'bg-zinc-400',
  }
  return <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${colors[tone]}`} />
}

function SourceCard({
  name,
  subtitle,
  status,
  message,
  count,
  lastSync,
  loading,
}: {
  name: string
  subtitle: string
  status: string
  message: string
  count: number
  lastSync: string | null
  loading?: boolean
}) {
  const conn = sourceConnectionLabel(status)

  return (
    <div className="flex gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900">
      <StatusDot tone={loading ? 'neutral' : conn.tone} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-50">{name}</p>
            <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{subtitle}</p>
          </div>
          <span
            className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
              conn.tone === 'connected'
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300'
                : conn.tone === 'demo'
                  ? 'bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-300'
                  : conn.tone === 'error'
                    ? 'bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-300'
                    : 'bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200'
            }`}
          >
            {loading ? '…' : conn.label}
          </span>
        </div>
        <p className="mt-2 text-[12px] leading-relaxed text-zinc-600 dark:text-zinc-300">
          {loading ? 'Loading…' : message}
        </p>
        <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[11px]">
          <div>
            <dt className="text-zinc-400 dark:text-zinc-500">Records</dt>
            <dd className="font-medium text-zinc-800 dark:text-zinc-100">{loading ? '—' : count}</dd>
          </div>
          <div>
            <dt className="text-zinc-400 dark:text-zinc-500">Last sync</dt>
            <dd className="font-medium text-zinc-800 dark:text-zinc-100">{formatLastSync(lastSync)}</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const options: { value: Theme; label: string }[] = [
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
  ]

  return (
    <div className="inline-flex rounded-lg border border-zinc-200 bg-white p-1 dark:border-zinc-600 dark:bg-zinc-900">
      {options.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          onClick={() => setTheme(value)}
          className={`rounded-md px-5 py-2 text-[13px] font-medium transition-colors ${
            theme === value
              ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-700 dark:text-zinc-50'
              : 'text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

function ActionButton({
  children,
  href,
}: {
  children: ReactNode
  href?: string
}) {
  const className =
    'inline-flex items-center justify-center rounded-lg border border-zinc-300 bg-white px-4 py-2 text-[13px] font-medium text-zinc-800 transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800'

  if (href) {
    return (
      <a href={href} className={className}>
        {children}
      </a>
    )
  }

  return (
    <button type="button" className={className}>
      {children}
    </button>
  )
}

function sectionContent(
  id: SectionId,
  ctx: {
    sources: Sources | null
    sourcesError: string | null
    loadingSources: boolean
    lastSyncAt: string | null
  },
) {
  switch (id) {
    case 'sources':
      return (
        <>
          {ctx.sourcesError && (
            <p className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200">
              {ctx.sourcesError}
            </p>
          )}
          <div className="space-y-2">
            {SOURCE_ROWS.map(({ id: sourceId, subtitle }) => {
              const row = ctx.sources?.[sourceId]
              return (
                <SourceCard
                  key={sourceId}
                  name={
                    row?.name ??
                    (sourceId === 'orders'
                      ? 'Shopify'
                      : sourceId === 'settlements'
                        ? 'Razorpay'
                        : 'Bank / COD')
                  }
                  subtitle={subtitle}
                  status={row?.status ?? 'unknown'}
                  message={row?.message ?? (ctx.sourcesError ? 'Unavailable' : '')}
                  count={row?.count ?? 0}
                  lastSync={ctx.lastSyncAt}
                  loading={ctx.loadingSources && !row}
                />
              )
            })}
          </div>
        </>
      )
    case 'security':
      return <ActionButton>Manage security</ActionButton>
    case 'theme':
      return <ThemeToggle />
    case 'feedback':
      return (
        <ActionButton href="mailto:support@ledgr.ai?subject=Ledgr%20Feedback">
          Send feedback
        </ActionButton>
      )
  }
}

export function SettingsPage() {
  const { lastSyncAt } = useApp()
  const [sources, setSources] = useState<Sources | null>(null)
  const [sourcesError, setSourcesError] = useState<string | null>(null)
  const [loadingSources, setLoadingSources] = useState(true)
  const [openSection, setOpenSection] = useState<SectionId | null>(null)

  function toggleSection(id: SectionId) {
    setOpenSection((current) => (current === id ? null : id))
  }

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoadingSources(true)
      setSourcesError(null)
      try {
        const data = await api.getSources()
        if (!cancelled) setSources(data)
      } catch (err) {
        if (!cancelled) {
          setSourcesError(err instanceof ApiError ? err.message : 'Could not load sources')
        }
      } finally {
        if (!cancelled) setLoadingSources(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const ctx = { sources, sourcesError, loadingSources, lastSyncAt }

  return (
    <div className="mx-auto max-w-[560px] px-6 py-8 lg:px-8 lg:py-10">
      <h1 className="mb-6 text-[20px] font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        Settings
      </h1>

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
        {SECTIONS.map(({ id, title }) => (
          <div
            key={id}
            className="border-b border-zinc-100 last:border-b-0 dark:border-zinc-800"
          >
            <SettingsRow
              id={id}
              title={title}
              open={openSection === id}
              onToggle={toggleSection}
            >
              {sectionContent(id, ctx)}
            </SettingsRow>
          </div>
        ))}
      </div>
    </div>
  )
}
