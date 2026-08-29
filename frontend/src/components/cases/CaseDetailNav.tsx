import { Link } from 'react-router-dom'
import { caseDetailPath, caseQueuePath } from '../../lib/caseQueue'
import type { Case } from '../../types/case'

type CaseDetailNavProps = {
  filter: string | null
  prev: Case | null
  next: Case | null
  position: number
  total: number
}

function NavArrow({ direction }: { direction: 'left' | 'right' }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      className="h-4 w-4"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden
    >
      {direction === 'left' ? (
        <path d="M10 4L6 8l4 4" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
      )}
    </svg>
  )
}

const navBtn =
  'inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-2 text-[13px] font-medium transition-colors dark:border-zinc-700'

export function CaseDetailNav({ filter, prev, next, position, total }: CaseDetailNavProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <Link
        to={caseQueuePath(filter)}
        className={`${navBtn} text-zinc-600 hover:bg-zinc-50 dark:text-zinc-300 dark:hover:bg-zinc-800`}
      >
        <NavArrow direction="left" />
        Back to queue
      </Link>

      <div className="flex flex-wrap items-center gap-2">
        {position > 0 && total > 0 && (
          <span className="hidden text-[12px] tabular-nums text-zinc-400 sm:inline">
            Case {position} of {total}
          </span>
        )}
        {prev ? (
          <Link
            to={caseDetailPath(prev.case_id, filter)}
            className={`${navBtn} text-zinc-700 hover:bg-zinc-50 dark:text-zinc-200 dark:hover:bg-zinc-800`}
          >
            <NavArrow direction="left" />
            Previous case
          </Link>
        ) : (
          <span
            className={`${navBtn} cursor-not-allowed text-zinc-300 dark:text-zinc-600`}
            aria-disabled
          >
            <NavArrow direction="left" />
            Previous case
          </span>
        )}
        {next ? (
          <Link
            to={caseDetailPath(next.case_id, filter)}
            className={`${navBtn} bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200`}
          >
            Next case
            <NavArrow direction="right" />
          </Link>
        ) : (
          <span
            className={`${navBtn} cursor-not-allowed border-zinc-100 bg-zinc-100 text-zinc-400 dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-600`}
            aria-disabled
          >
            Next case
            <NavArrow direction="right" />
          </span>
        )}
      </div>
    </div>
  )
}