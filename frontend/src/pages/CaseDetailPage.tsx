import { Link, useParams } from 'react-router-dom'
import { useApp } from '../context/AppContext'

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const { cases } = useApp()
  const caseItem = cases.find((c) => c.case_id === caseId)

  return (
    <div className="mx-auto max-w-[1120px] px-6 py-8 lg:px-8 lg:py-10">
      <Link to="/cases" className="text-[13px] font-medium text-ledgr-primary hover:underline">
        ← Back to cases
      </Link>
      <h1 className="mt-4 text-[22px] font-semibold text-ledgr-ink">
        {caseItem ? caseItem.case_id : 'Case not found'}
      </h1>
      <p className="mt-2 text-[14px] text-ledgr-muted">
        Case ticket view will be built next.
      </p>
    </div>
  )
}
