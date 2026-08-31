import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { AskAiPanel } from '../components/AskAiPanel'
import { BackToCaseLink } from '../components/BackToCaseLink'
import { CaseAiAnalysisPanel } from '../components/cases/CaseAiAnalysisPanel'
import { CaseDetailNav } from '../components/cases/CaseDetailNav'
import { CaseDocumentsPanel } from '../components/cases/CaseDocumentsPanel'
import { CaseDraftMessagePanel } from '../components/cases/CaseDraftMessagePanel'
import { CaseRemittancePanel } from '../components/cases/CaseRemittancePanel'
import { CaseResolvedBanner } from '../components/cases/CaseTimeline'
import { CaseSummaryPanel } from '../components/cases/CaseSummaryPanel'
import { CaseTimeline } from '../components/cases/CaseTimeline'
import { useApp } from '../context/AppContext'
import { api, ApiError } from '../lib/api'
import {
  caseDisplayId,
  caseStatusBadgeClass,
  caseStatusLabel,
} from '../lib/caseDisplay'
import { isOpenForReview, canReopenCase } from '../lib/caseUtils'
import { caseNeighbors, caseQueuePath, filterCases } from '../lib/caseQueue'
import type { Case } from '../types/case'

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const [searchParams] = useSearchParams()
  const filter = searchParams.get('filter')
  const { cases, refresh } = useApp()

  const [caseItem, setCaseItem] = useState<Case | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [acting, setActing] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)
  const [manualComment, setManualComment] = useState('')
  const [reopenOpen, setReopenOpen] = useState(false)
  const [reopenReason, setReopenReason] = useState('')

  const loadCase = useCallback(async () => {
    if (!caseId) return
    setLoadError(null)
    const cached = cases.find((c) => c.case_id === caseId)
    if (cached) setCaseItem(cached)

    try {
      const fresh = await api.getCase(caseId)
      setCaseItem(fresh)
    } catch (err) {
      if (!cached) {
        setLoadError(err instanceof ApiError ? err.message : 'Failed to load case')
      }
    } finally {
      setLoading(false)
    }
  }, [caseId, cases])

  useEffect(() => {
    setLoading(true)
    loadCase()
  }, [loadCase])

  const queue = useMemo(() => filterCases(cases, filter), [cases, filter])
  const { prev, next, position, total } = useMemo(
    () => caseNeighbors(queue, caseId ?? ''),
    [queue, caseId],
  )

  async function afterMutation(updated: Case) {
    setCaseItem(updated)
    setManualOpen(false)
    setManualComment('')
    await refresh()
  }

  async function handleAccept() {
    if (!caseItem || acting) return
    setActing(true)
    setActionError(null)
    try {
      const updated = await api.resolveCase(caseItem.case_id, 'accepted')
      await afterMutation(updated)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not accept recommendation')
    } finally {
      setActing(false)
    }
  }

  async function handleManualResolve() {
    if (!caseItem || acting) return
    const comment = manualComment.trim()
    if (!comment) {
      setActionError('A comment is required when keeping a case for manual review.')
      return
    }
    setActing(true)
    setActionError(null)
    try {
      const updated = await api.resolveCase(caseItem.case_id, 'manual_review', comment)
      await afterMutation(updated)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not save resolution')
    } finally {
      setActing(false)
    }
  }

  async function handleReopen() {
    if (!caseItem || acting) return
    const reason = reopenReason.trim()
    if (!reason) {
      setActionError('A reason is required to reopen this case.')
      return
    }
    setActing(true)
    setActionError(null)
    try {
      const updated = await api.reopenCase(caseItem.case_id, reason)
      setReopenOpen(false)
      setReopenReason('')
      await afterMutation(updated)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not reopen case')
    } finally {
      setActing(false)
    }
  }

  async function handleRetryAi() {
    if (!caseItem || acting) return
    setActing(true)
    setActionError(null)
    try {
      const updated = await api.retryAi(caseItem.case_id)
      setCaseItem(updated)
      await refresh()
    } catch (err) {
      setActionError(
        err instanceof ApiError && err.status === 429
          ? 'Every AI provider is rate-limited right now. Try again shortly.'
          : err instanceof Error
            ? err.message
            : 'Could not retry the investigation',
      )
    } finally {
      setActing(false)
    }
  }

  /**
   * The one controlled agentic step: AI named evidence it was missing, so we
   * fetch what is realistically available and ask for ONE more verdict.
   * User-triggered only, never automatic, and never looped further.
   */
  async function handleInvestigateFurther() {
    if (!caseItem || acting) return
    setActing(true)
    setActionError(null)
    try {
      const updated = await api.investigateFurther(caseItem.case_id)
      setCaseItem(updated)
      await refresh()
    } catch (err) {
      setActionError(
        err instanceof ApiError && err.status === 429
          ? 'Every AI provider is rate-limited right now. Try again shortly.'
          : err instanceof Error
            ? err.message
            : 'Could not complete the follow-up investigation',
      )
    } finally {
      setActing(false)
    }
  }

  async function handleBookmark() {
    if (!caseItem || acting) return
    setActing(true)
    setActionError(null)
    try {
      await api.toggleBookmark(caseItem.case_id)
      await loadCase()
      await refresh()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not update bookmark')
    } finally {
      setActing(false)
    }
  }

  if (loading && !caseItem) {
    return (
      <div className="mx-auto max-w-[1120px] space-y-4 px-6 py-6 lg:px-8">
        <CaseDetailNav filter={filter} prev={prev} next={next} position={position} total={total} />
        <p className="text-[14px] text-zinc-500">Loading case…</p>
      </div>
    )
  }

  if (!caseItem) {
    return (
      <div className="mx-auto max-w-[1120px] space-y-4 px-6 py-6 lg:px-8">
        <CaseDetailNav filter={filter} prev={prev} next={next} position={position} total={total} />
        <p className="text-[15px] text-zinc-700">{loadError ?? 'Case not found'}</p>
      </div>
    )
  }

  const displayId = caseDisplayId(caseItem)
  const resolved = Boolean(caseItem.resolution?.resolved)
  const reopenable = canReopenCase(caseItem)
  const canDecide = isOpenForReview(caseItem) && !acting
  // Only offer the follow-up when AI actually named something it was missing —
  // otherwise there is nothing new to fetch and the extra call would be waste.
  const missingEvidence = caseItem.ai?.missing_evidence ?? []
  const canInvestigateFurther = !resolved && missingEvidence.length > 0

  return (
    <div className="mx-auto max-w-[1120px] space-y-6 px-6 py-6 lg:px-8 lg:py-8">
      <BackToCaseLink />

      <CaseDetailNav filter={filter} prev={prev} next={next} position={position} total={total} />

      <div>
        <Link
          to={caseQueuePath(filter)}
          className="text-[13px] font-medium text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
        >
          AI Review Queue
        </Link>
        <span className="mx-2 text-zinc-300">/</span>
        <span className="text-[13px] font-medium text-zinc-800 dark:text-zinc-200">{displayId}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[22px] font-semibold text-zinc-900 dark:text-zinc-50">{displayId}</h1>
            <span
              className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${caseStatusBadgeClass(caseItem.case_status, resolved)}`}
            >
              {caseStatusLabel(caseItem)}
            </span>
          </div>
          <p className="mt-1 text-[13px] text-zinc-500">{caseItem.case_id}</p>
        </div>

        {!resolved && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={acting}
              onClick={handleBookmark}
              title="Bookmark for quick access"
              className={`rounded-lg border px-3 py-2 text-[13px] font-medium transition-colors ${
                caseItem.bookmarked
                  ? 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200'
                  : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800'
              }`}
            >
              {caseItem.bookmarked ? 'Bookmarked' : 'Bookmark'}
            </button>
          </div>
        )}
      </div>

      {resolved && (
        <CaseResolvedBanner
          caseItem={caseItem}
          canReopen={reopenable}
          onReopen={() => {
            setReopenOpen(true)
            setActionError(null)
          }}
        />
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <CaseSummaryPanel caseItem={caseItem} />
        <CaseAiAnalysisPanel caseItem={caseItem} />
        <CaseDocumentsPanel caseId={caseItem.case_id} />
      </div>

      {!resolved && (
        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-zinc-100 pt-6 dark:border-zinc-800">
          {caseItem.case_status === 'ai_pending' && (
            <button
              type="button"
              disabled={acting}
              onClick={handleRetryAi}
              title="AI could not reach a verdict earlier. Try again."
              className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-[14px] font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-300"
            >
              {acting ? 'Retrying…' : 'Retry AI investigation'}
            </button>
          )}

          {canInvestigateFurther && (
            <button
              type="button"
              disabled={acting}
              onClick={handleInvestigateFurther}
              title={`AI asked for: ${missingEvidence.join('; ')}`}
              className="rounded-lg border border-violet-200 bg-violet-50 px-4 py-2.5 text-[14px] font-medium text-violet-700 transition-colors hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300"
            >
              {acting ? 'Investigating…' : 'Investigate further'}
            </button>
          )}

          <button
            type="button"
            disabled={!canDecide}
            onClick={() => {
              setManualOpen(true)
              setActionError(null)
            }}
            className="rounded-lg border border-zinc-200 px-4 py-2.5 text-[14px] font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
          >
            Resolve manually
          </button>
          <button
            type="button"
            disabled={!canDecide || caseItem.case_status === 'ai_pending'}
            onClick={handleAccept}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {acting ? 'Saving…' : 'Accept recommendation'}
          </button>
        </div>
      )}

      {reopenOpen && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-5 dark:border-amber-500/30 dark:bg-amber-950/20">
          <p className="text-[14px] font-medium text-zinc-900 dark:text-zinc-50">Reopen for review</p>
          <p className="mt-1 text-[13px] text-zinc-600 dark:text-zinc-400">
            Use this if the case was resolved by mistake. It will return to the open review queue.
          </p>
          <textarea
            value={reopenReason}
            onChange={(e) => setReopenReason(e.target.value)}
            rows={3}
            placeholder="Why are you reopening this case?"
            className="mt-3 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[13px] text-zinc-800 outline-none ring-blue-500/0 focus:ring-2 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
          />
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setReopenOpen(false)
                setReopenReason('')
              }}
              className="rounded-lg px-3 py-2 text-[13px] font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={acting}
              onClick={handleReopen}
              className="rounded-lg bg-amber-700 px-4 py-2 text-[13px] font-medium text-white hover:bg-amber-800 dark:bg-amber-600 dark:hover:bg-amber-500"
            >
              {acting ? 'Reopening…' : 'Send back to review'}
            </button>
          </div>
        </div>
      )}

      {manualOpen && (
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-5 dark:border-zinc-700 dark:bg-zinc-800/40">
          <p className="text-[14px] font-medium text-zinc-900 dark:text-zinc-50">Resolve manually</p>
          <p className="mt-1 text-[13px] text-zinc-500">
            Add a comment explaining why this case needs manual review.
          </p>
          <textarea
            value={manualComment}
            onChange={(e) => setManualComment(e.target.value)}
            rows={3}
            placeholder="Describe what needs manual follow-up…"
            className="mt-3 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[13px] text-zinc-800 outline-none ring-blue-500/0 focus:ring-2 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
          />
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setManualOpen(false)}
              className="rounded-lg px-3 py-2 text-[13px] font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={acting}
              onClick={handleManualResolve}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-[13px] font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900"
            >
              Save resolution
            </button>
          </div>
        </div>
      )}

      {actionError && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-[13px] text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200">
          {actionError}
        </p>
      )}

      <section
        id="case-timeline"
        className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900"
      >
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Case timeline</h2>
        <div className="mt-4">
          <CaseTimeline history={caseItem.history ?? []} />
        </div>
      </section>

      {/* Scoped to this case: the backend passes only this case's own records
          as context, so answers can't drift onto unrelated data. Read-only —
          asking never changes the case's status or resolution. */}
      {/* Renders only when this case actually has courier remittance detail,
          so it never shows as an empty section on the other cases. */}
      <CaseRemittancePanel caseItem={caseItem} />

      <CaseDraftMessagePanel caseId={caseItem.case_id} />

      <AskAiPanel caseId={caseItem.case_id} />
    </div>
  )
}
