import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../lib/api'

/**
 * Ask AI — grounded question answering over the merchant's own data.
 *
 * The backend answers most questions directly from the persisted case store
 * with pandas (zero API cost) and only calls a model for genuinely novel
 * questions. `source` tells us which path ran, and we surface that honestly
 * rather than implying every answer came from an LLM.
 *
 * Read-only by design: asking a question never changes a case's status or
 * resolution.
 */
type Turn = {
  question: string
  answer: string
  /** Which provider answered — 'python' means the deterministic fallback. */
  source: string
}

type AskAiPanelProps = {
  /** Scopes the question to one case. Omit for the global assistant. */
  caseId?: string
  compact?: boolean
}

const GLOBAL_SUGGESTIONS = [
  'Which orders are still pending?',
  'How much is outstanding?',
  'Which cases are waiting on AI?',
]

const CASE_SUGGESTIONS = [
  'Why is this flagged?',
  'What evidence is missing?',
  'What should I do next?',
]

export function AskAiPanel({ caseId, compact = false }: AskAiPanelProps) {
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Start a fresh conversation whenever the case changes.
  //
  // Navigating /cases/A -> /cases/B keeps this component MOUNTED (same route,
  // different param), so without this the previous case's Q&A stayed on
  // screen -- and, worse, was still sent as `history` on the next case's
  // questions. A question about case B answered with case A's context is a
  // wrong answer about real money, not just stale UI.
  //
  // Done inside the component rather than with a key={caseId} at the call
  // site, so no future call site can forget it.
  useEffect(() => {
    setTurns([])
    setQuestion('')
    setError(null)
  }, [caseId])

  const suggestions = caseId ? CASE_SUGGESTIONS : GLOBAL_SUGGESTIONS

  async function ask(q: string) {
    const trimmed = q.trim()
    if (!trimmed || busy) return
    setBusy(true)
    setError(null)
    try {
      // Send recent turns so follow-ups have an antecedent.
      const res = await api.askAi(
        trimmed, caseId,
        turns.slice(-6).map((t) => ({ question: t.question, answer: t.answer })),
      )
      setTurns((prev) => [...prev, { question: trimmed, answer: res.answer, source: res.source }])
      setQuestion('')
    } catch (err) {
      // 429 means every provider is rate-limited — say that plainly rather
      // than showing a generic failure the user can't act on.
      if (err instanceof ApiError && err.status === 429) {
        setError('All AI providers are currently rate-limited. Try again shortly.')
      } else if (err instanceof ApiError && err.status === 503) {
        setError('AI is temporarily unavailable.')
      } else {
        setError(err instanceof Error ? err.message : 'Something went wrong')
      }
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    ask(question)
  }

  return (
    <div className={compact ? '' : 'rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900'}>
      {!compact && (
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">
          {caseId ? 'Ask AI about this case' : 'Ask AI'}
        </h2>
      )}

      {turns.length > 0 && (
        <div className="mb-3 max-h-64 space-y-3 overflow-y-auto pt-3">
          {turns.map((t, i) => (
            <div key={i}>
              <p className="text-[12.5px] font-medium text-zinc-500 dark:text-zinc-400">
                {t.question}
              </p>
              <p className="mt-1 whitespace-pre-wrap text-[13px] leading-relaxed text-zinc-800 dark:text-zinc-200">
                {t.answer}
              </p>
              <p className="mt-1 text-[11px] text-zinc-400 dark:text-zinc-500">
                {t.source === 'python'
                  ? 'AI unavailable — answered directly from your data'
                  : `Answered by AI (${t.source})`}
              </p>
            </div>
          ))}
        </div>
      )}

      {turns.length === 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              disabled={busy}
              onClick={() => ask(s)}
              className="rounded-full border border-zinc-200 px-2.5 py-1 text-[12px] text-zinc-600 transition-colors hover:border-zinc-300 hover:text-zinc-900 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-100"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={onSubmit} className="mt-3 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={caseId ? 'Ask about this case…' : 'Ask about your reconciliation data…'}
          disabled={busy}
          className="min-w-0 flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-[13px] text-zinc-900 outline-none placeholder:text-zinc-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:ring-blue-900/40"
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-400 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-600"
        >
          {busy ? 'Asking…' : 'Ask'}
        </button>
      </form>

      {error && (
        <p className="mt-2 text-[12.5px] text-amber-700 dark:text-amber-500">{error}</p>
      )}

      <p className="mt-2 text-[11px] text-zinc-400 dark:text-zinc-500">
        Answers are based only on your reconciliation data in Ledgr.
      </p>
    </div>
  )
}
