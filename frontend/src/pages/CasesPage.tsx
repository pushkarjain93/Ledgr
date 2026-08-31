import { useLayoutEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CaseFilterBar, filterTitle } from '../components/cases/CaseFilterBar'
import { CasesTable } from '../components/cases/CasesTable'
import { useApp } from '../context/AppContext'
import { filterCases } from '../lib/caseQueue'
import { scrollAppMainToTop } from '../lib/scrollAppMain'

export function CasesPage() {
  const [params] = useSearchParams()
  const filter = params.get('filter')
  const { cases, aiInProgress } = useApp()
  const topRef = useRef<HTMLDivElement>(null)

  const filtered = useMemo(() => filterCases(cases, filter), [cases, filter])
  const title = filterTitle(filter)

  useLayoutEffect(() => {
    scrollAppMainToTop()
    topRef.current?.scrollIntoView({ block: 'start' })
  }, [filter])

  return (
    <div ref={topRef} className="mx-auto max-w-[1120px] space-y-5 px-6 py-5 lg:px-8 lg:py-6">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">AI Review Queue</p>
        <h1 className="mt-1 text-[22px] font-semibold text-zinc-900 dark:text-zinc-50">{title}</h1>
        <p className="mt-1.5 text-[14px] text-zinc-500">
          {filtered.length} {filtered.length === 1 ? 'case' : 'cases'}
          {filter === 'resolved' || filter === 'bookmarked' ? '' : ' open'}
        </p>
        {/* Reconciliation finishes in about a second; AI verdicts land after.
            Say so, rather than leaving rows looking permanently unanalysed. */}
        {aiInProgress > 0 && (
          <p className="mt-1.5 flex items-center gap-2 text-[13px] text-blue-600 dark:text-blue-400">
            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
            AI is investigating {aiInProgress} case{aiInProgress === 1 ? '' : 's'} — results appear automatically
          </p>
        )}
      </div>

      <CaseFilterBar />

      <section className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
        <CasesTable
          cases={filtered}
          filter={filter}
          emptyMessage={
            filter === 'resolved'
              ? 'No resolved cases yet.'
              : filter === 'bookmarked'
                ? 'No bookmarked cases yet. Bookmark a case from its ticket page.'
                : 'No open cases match this filter.'
          }
        />
      </section>
    </div>
  )
}
