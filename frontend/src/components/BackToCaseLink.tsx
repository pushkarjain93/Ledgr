import { Link, useSearchParams } from 'react-router-dom'

/**
 * "Back to <case>" shown when the user arrived here by following an AI
 * cross-reference (`?from=CASE-...`).
 *
 * Following a reference out of a case and having no route home is worse than
 * not linking at all — you lose your place in the review queue and have to
 * navigate back by memory.
 */
export function BackToCaseLink() {
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from')
  if (!from) return null

  return (
    <Link
      to={`/cases/${from}`}
      className="mb-4 inline-flex items-center gap-1.5 text-[13px] font-medium text-blue-600 hover:underline dark:text-blue-400"
    >
      <span aria-hidden>←</span> Back to {from.replace(/^CASE-/, '')}
    </Link>
  )
}
