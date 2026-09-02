import { Link, useSearchParams } from 'react-router-dom'

const FILTERS = [
  { key: '', label: 'All open' },
  { key: 'needs_decision', label: 'AI recommendation' },
  { key: 'needs_investigation', label: 'Needs investigation' },
  { key: 'has_notes', label: 'My notes' },
  { key: 'bookmarked', label: 'Bookmarked' },
  { key: 'resolved', label: 'Resolved' },
] as const

export function CaseFilterBar() {
  const [params, setParams] = useSearchParams()
  const active = params.get('filter') ?? ''

  return (
    <div className="flex flex-wrap gap-2">
      {FILTERS.map(({ key, label }) => {
        const selected = active === key
        const to = key ? `/cases?filter=${key}` : '/cases'
        return (
          <Link
            key={key || 'all'}
            to={to}
            onClick={(e) => {
              e.preventDefault()
              setParams(key ? { filter: key } : {})
            }}
            className={`rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors ${
              selected
                ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                : 'bg-white text-zinc-600 ring-1 ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800'
            }`}
          >
            {label}
          </Link>
        )
      })}
    </div>
  )
}

export function filterTitle(filter: string | null): string {
  return FILTERS.find((f) => f.key === (filter ?? ''))?.label ?? 'Cases'
}
