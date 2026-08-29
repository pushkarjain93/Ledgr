import type { Sources } from '../../lib/api'
import { formatLastSync, sourceConnectionLabel, SOURCE_ROWS } from '../../lib/sourceStatus'

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
  loading,
}: {
  name: string
  subtitle: string
  status: string
  message: string
  count: number
  loading?: boolean
}) {
  const conn = sourceConnectionLabel(status)

  return (
    <div className="flex gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900">
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
        <p className="mt-2 text-[11px] text-zinc-500 dark:text-zinc-400">
          <span className="text-zinc-400 dark:text-zinc-500">Records </span>
          <span className="font-medium text-zinc-800 dark:text-zinc-100">
            {loading ? '—' : count}
          </span>
        </p>
      </div>
    </div>
  )
}

type SourceCardsProps = {
  sources: Sources | null
  loading: boolean
  error: string | null
}

export function SourceCards({ sources, loading, error }: SourceCardsProps) {
  return (
    <section>
      <div className="mb-3">
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Data sources</h2>
        <p className="mt-0.5 text-[12.5px] text-zinc-500 dark:text-zinc-400">
          Connection status before each sync
        </p>
      </div>

      {error && (
        <p className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {SOURCE_ROWS.map(({ id, subtitle }) => {
          const row = sources?.[id]
          return (
            <SourceCard
              key={id}
              name={
                row?.name ??
                (id === 'orders'
                  ? 'Shopify'
                  : id === 'settlements'
                    ? 'Razorpay'
                    : 'Bank / COD')
              }
              subtitle={subtitle}
              status={row?.status ?? 'unknown'}
              message={row?.message ?? (error ? 'Unavailable' : '')}
              count={row?.count ?? 0}
              loading={loading && !row}
            />
          )
        })}
      </div>
    </section>
  )
}

export function formatNextBatchAt(iso: string): string {
  const at = new Date(iso)
  return at.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export { formatLastSync }
