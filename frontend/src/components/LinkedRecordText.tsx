import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import type { Case } from '../types/case'

/**
 * Renders AI text with any order/settlement ID turned into a link.
 *
 * The model reasons across records — "STL-00080 is already matched to
 * ORD-00011" — and without links the user has to copy that ID and go hunting
 * through Transactions or Cases to check the claim. Making every referenced
 * record one click away is what turns the reasoning into something verifiable.
 *
 * Where a link points:
 *   - the record has an open case  -> that case, so the full context is there
 *   - otherwise                    -> Transactions, pre-filtered to that record
 *
 * Nothing is invented: only IDs matching the real ORD-/STL- patterns are
 * linked, and the surrounding text is left exactly as written.
 */
const RECORD_ID = /\b((?:ORD|STL)-[A-Z0-9-]+)\b/g

type LinkedRecordTextProps = {
  text: string | null | undefined
  cases: Case[]
  /** Don't link the case the user is already looking at. */
  currentRecordId?: string
  /** Case being viewed, passed to the destination so it can offer "back". */
  currentCaseId?: string
}

export function LinkedRecordText({ text, cases, currentRecordId, currentCaseId }: LinkedRecordTextProps) {
  if (!text) return null

  const caseByRecord = new Map(cases.map((c) => [c.record_id, c]))
  const parts = text.split(RECORD_ID)

  return (
    <>
      {parts.map((part, i) => {
        // split() with one capture group puts matches at odd indices.
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>

        if (part === currentRecordId) {
          return (
            <span key={i} className="font-medium text-zinc-800 dark:text-zinc-200">
              {part}
            </span>
          )
        }

        const linked = caseByRecord.get(part)
        // Carry where we came from, so the destination can offer a way back.
        // Following a reference out of a case and having no route home is
        // worse than not linking at all.
        const from = currentCaseId ? `&from=${encodeURIComponent(currentCaseId)}` : ''
        const href = linked
          ? `/cases/${linked.case_id}${currentCaseId ? `?from=${encodeURIComponent(currentCaseId)}` : ''}`
          : `/transactions?search=${encodeURIComponent(part)}${from}`

        return (
          <Link
            key={i}
            to={href}
            title={linked ? 'Open this case' : 'Find this record in Transactions'}
            className="font-medium text-blue-600 underline decoration-blue-300 underline-offset-2 hover:decoration-blue-600 dark:text-blue-400"
          >
            {part}
          </Link>
        )
      })}
    </>
  )
}
