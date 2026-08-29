import { useSearchParams } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { needsHumanDecision, isUnresolved } from '../lib/caseUtils'

const FILTER_LABELS: Record<string, string> = {
  needs_decision: 'Needs your decision',
  ai_pending: 'Waiting on AI',
  pending_settlement: 'Awaiting settlement',
}

export function CasesPage() {
  const [params] = useSearchParams()
  const filter = params.get('filter')
  const { cases } = useApp()

  let filtered = cases.filter(isUnresolved)
  if (filter === 'needs_decision') {
    filtered = filtered.filter(needsHumanDecision)
  } else if (filter === 'ai_pending') {
    filtered = filtered.filter((c) => c.case_status === 'ai_pending')
  } else if (filter === 'pending_settlement') {
    filtered = filtered.filter((c) => c.case_status === 'pending_settlement')
  }

  const title = filter ? FILTER_LABELS[filter] ?? 'Cases' : 'Cases'

  return (
    <div className="mx-auto max-w-[1120px] px-6 py-8 lg:px-8 lg:py-10">
      <h1 className="text-[22px] font-semibold text-ledgr-ink">{title}</h1>
      <p className="mt-2 text-[14px] text-ledgr-muted">
        {filtered.length} open {filtered.length === 1 ? 'case' : 'cases'}
        {filter ? ' matching this filter' : ''}. Full case management UI coming next.
      </p>
    </div>
  )
}
