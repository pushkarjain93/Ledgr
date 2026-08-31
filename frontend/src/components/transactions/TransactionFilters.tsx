import type { TransactionFilters as Filters, TransactionStatusFilter } from '../../lib/transactionDisplay'
import { todayISO } from '../../lib/merchantState'

const STATUS_OPTIONS: { value: TransactionStatusFilter; label: string }[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'matched', label: 'Matched' },
  { value: 'ai_review', label: 'AI review' },
  { value: 'awaiting_settlement', label: 'Awaiting settlement' },
  { value: 'exception', label: 'Exception' },
]

function formatPaymentModeLabel(mode: string): string {
  return mode.replace(/_/g, ' ')
}

type TransactionFiltersProps = {
  filters: Filters
  paymentModes: string[]
  /** Tier options present in the data, already labelled and ordered. */
  tiers: { value: string; label: string }[]
  onChange: (next: Filters) => void
}

export function TransactionFiltersBar({
  filters,
  paymentModes,
  tiers,
  onChange,
}: TransactionFiltersProps) {
  const today = todayISO()

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
      <div className="relative min-w-0 flex-1">
        <svg
          viewBox="0 0 20 20"
          fill="none"
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden
        >
          <circle cx="9" cy="9" r="5.5" />
          <path d="M13.5 13.5L17 17" strokeLinecap="round" />
        </svg>
        <input
          type="search"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search record ID, settlement, reason…"
          className="w-full rounded-lg border border-zinc-200 bg-white py-2.5 pl-9 pr-3 text-[13px] text-zinc-800 outline-none ring-blue-500/0 focus:ring-2 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <div className="flex items-center rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900">
          <label htmlFor="transaction-date-filter" className="sr-only">
            Filter by date
          </label>
          <input
            id="transaction-date-filter"
            type="date"
            value={filters.date}
            max={today}
            onChange={(e) => onChange({ ...filters, date: e.target.value })}
            className="border-0 bg-transparent text-[13px] text-zinc-700 outline-none focus:ring-0 dark:text-zinc-200"
          />
          {filters.date && (
            <button
              type="button"
              aria-label="Clear date filter"
              onClick={() => onChange({ ...filters, date: '' })}
              className="ml-2 rounded p-0.5 text-zinc-400 transition-colors hover:text-zinc-600 dark:hover:text-zinc-200"
            >
              <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5" stroke="currentColor" strokeWidth="1.5">
                <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
              </svg>
            </button>
          )}
        </div>

        <select
          value={filters.paymentMode}
          onChange={(e) => onChange({ ...filters, paymentMode: e.target.value })}
          aria-label="Filter by payment mode"
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[13px] text-zinc-700 outline-none ring-blue-500/0 focus:ring-2 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200"
        >
          <option value="all">All payment modes</option>
          {paymentModes.map((mode) => (
            <option key={mode} value={mode}>
              {formatPaymentModeLabel(mode)}
            </option>
          ))}
        </select>

        {/* Tier answers "which rule settled this?" — the one thing the table
            showed but could not be narrowed by. Options are derived from the
            data, so a tier with no records is never offered. */}
        <select
          value={filters.tier}
          onChange={(e) => onChange({ ...filters, tier: e.target.value })}
          aria-label="Filter by reconciliation tier"
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[13px] text-zinc-700 outline-none ring-blue-500/0 focus:ring-2 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200"
        >
          <option value="all">All tiers</option>
          {tiers.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        <select
          value={filters.status}
          onChange={(e) =>
            onChange({ ...filters, status: e.target.value as TransactionStatusFilter })
          }
          aria-label="Filter by status"
          className="rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[13px] text-zinc-700 outline-none ring-blue-500/0 focus:ring-2 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200"
        >
          {STATUS_OPTIONS.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
