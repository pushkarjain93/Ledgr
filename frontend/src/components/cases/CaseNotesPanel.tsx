import { useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import type { Case } from '../../types/case'

/**
 * Working notes — a partial finding recorded WITHOUT resolving the case.
 *
 * The gap this fills: a reviewer often learns something that does not settle
 * the case ("chased the courier, awaiting reply", "customer says they paid by
 * UPI"). Before this, the only way to write that down was to resolve the case
 * as manual review, which took it out of the queue. So the finding either went
 * into someone's head or the case got closed prematurely.
 *
 * Saving a note leaves case_status untouched — it stays open, stays in the
 * queue, and is findable later through the "My notes" filter.
 */
export function CaseNotesPanel({
  caseItem,
  onSaved,
}: {
  caseItem: Case
  onSaved: (updated: Case) => void
}) {
  const [text, setText] = useState(caseItem.comment ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  // Re-seed when navigating between cases — this component stays mounted
  // across /cases/A -> /cases/B, so without this the previous case's note
  // would sit in the box and could be saved onto the wrong case.
  useEffect(() => {
    setText(caseItem.comment ?? '')
    setError(null)
    setSavedAt(null)
  }, [caseItem.case_id, caseItem.comment])

  const resolved = Boolean(caseItem.resolution?.resolved)
  const dirty = text.trim() !== (caseItem.comment ?? '').trim()

  async function handleSave() {
    if (saving || !dirty) return
    setSaving(true)
    setError(null)
    try {
      const updated = await api.setComment(caseItem.case_id, text.trim())
      onSaved(updated)
      setSavedAt(Date.now())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the note')
    } finally {
      setSaving(false)
    }
  }

  if (resolved) {
    // A resolved case keeps its note as part of the record, but editing it
    // would rewrite history on a closed decision.
    if (!caseItem.comment?.trim()) return null
    return (
      <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Working notes</h2>
        <p className="mt-3 whitespace-pre-wrap text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-300">
          {caseItem.comment}
        </p>
      </section>
    )
  }

  return (
    <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Working notes</h2>
        {caseItem.comment?.trim() && !dirty && (
          <span className="rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
            Saved · case still open
          </span>
        )}
      </div>
      <p className="mt-0.5 text-[12.5px] text-zinc-500 dark:text-zinc-400">
        Record what you found so far. This does <strong>not</strong> resolve the case — it stays
        in the queue, and you can find it again under the “My notes” filter.
      </p>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        placeholder="e.g. Chased BLUEDART on 2 Sep, awaiting their remittance file…"
        className="mt-3 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[13px] leading-relaxed text-zinc-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:ring-blue-900/40"
      />

      {error && (
        <p className="mt-2 text-[12.5px] text-red-600 dark:text-red-400">{error}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !dirty}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          {saving ? 'Saving…' : 'Save note'}
        </button>
        {savedAt && !dirty && (
          <span className="text-[12.5px] text-emerald-600 dark:text-emerald-400">
            Note saved — case left open for later.
          </span>
        )}
      </div>
    </section>
  )
}
