import { LinkedRecordText } from '../LinkedRecordText'
import { useApp } from '../../context/AppContext'
import type { Case } from '../../types/case'

type CaseAiAnalysisPanelProps = {
  caseItem: Case
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5 shrink-0 text-emerald-600" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 8l2.5 2.5L12 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function CaseAiAnalysisPanel({ caseItem }: CaseAiAnalysisPanelProps) {
  const { cases } = useApp()
  const ai = caseItem.ai
  const finding = ai?.reason?.trim() || caseItem.explanation || 'No AI finding available yet.'
  const recommendation = ai?.next_step?.trim() || '—'
  const evidence = ai?.evidence ?? []
  const followup = ai?.followup ?? null
  const rawUnavailable = followup?.still_unavailable
  const unavailable = Array.isArray(rawUnavailable)
    ? rawUnavailable
    : rawUnavailable
      ? [String(rawUnavailable)]
      : []

  return (
    <section
      id="case-ai-analysis"
      className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">AI Analysis</h2>
        {followup && (
          <span className="rounded-full bg-violet-50 px-2.5 py-0.5 text-[11px] font-medium text-violet-700 dark:bg-violet-500/15 dark:text-violet-300">
            Updated by deeper investigation
          </span>
        )}
      </div>

      {/* What "Investigate further" actually did. Shown ABOVE the finding
          because it is the newest information on the page, and because a
          re-confirmed verdict otherwise reads as though the button did
          nothing. */}
      {followup && (
        <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50/50 p-3.5 dark:border-violet-500/25 dark:bg-violet-500/[0.07]">
          <p className="text-[11px] font-medium uppercase tracking-wide text-violet-700 dark:text-violet-300">
            What the deeper look found
          </p>
          <p className="mt-2 text-[13px] font-medium leading-relaxed text-zinc-800 dark:text-zinc-100">
            {followup.changed
              ? 'New evidence changed the recommendation.'
              : 'The original finding was re-checked and still holds.'}
          </p>
          {followup.evidence_checked.length > 0 && (
            <ul className="mt-2.5 space-y-1.5">
              {followup.evidence_checked.map((item) => (
                <li key={item} className="flex items-start gap-2 text-[12.5px] text-zinc-700 dark:text-zinc-300">
                  <CheckIcon />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
          {followup.changed && followup.previous.next_step && (
            <p className="mt-2.5 text-[12px] leading-relaxed text-zinc-500 dark:text-zinc-400">
              Previously advised:{' '}
              <span className="line-through decoration-zinc-400">
                {followup.previous.next_step}
              </span>
            </p>
          )}
          {/* Tolerate a bare string as well as a list. The backend sends a
              list, but this panel blanking the whole case page over a shape
              mismatch is a far worse failure than a slightly odd sentence. */}
          {unavailable.length > 0 && (
            <p className="mt-2.5 text-[12px] leading-relaxed text-zinc-500 dark:text-zinc-400">
              Could not check: {unavailable.join(', ')}.
            </p>
          )}
        </div>
      )}

      {ai?.error && (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200">
          {ai.error}
        </p>
      )}

      <div className="mt-4">
        <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">Finding</p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-700 dark:text-zinc-300">
          <LinkedRecordText text={finding} cases={cases} currentRecordId={caseItem.record_id} currentCaseId={caseItem.case_id} />
        </p>
      </div>

      {evidence.length > 0 && (
        <div className="mt-5">
          <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">Evidence</p>
          <ul className="mt-2 space-y-2">
            {evidence.map((item) => (
              <li key={item} className="flex items-start gap-2 text-[13px] text-zinc-600 dark:text-zinc-300">
                <CheckIcon />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 rounded-lg border border-blue-100 bg-blue-50/60 px-3.5 py-3 dark:border-blue-500/20 dark:bg-blue-500/10">
        <p className="text-[11px] font-medium uppercase tracking-wide text-blue-600 dark:text-blue-400">
          AI Recommendation
        </p>
        <p className="mt-1 text-[13px] font-medium leading-relaxed text-zinc-800 dark:text-zinc-100">
          <LinkedRecordText text={recommendation} cases={cases} currentRecordId={caseItem.record_id} currentCaseId={caseItem.case_id} />
        </p>
      </div>

      {(ai?.missing_evidence?.length ?? 0) > 0 && (
        <div className="mt-4">
          <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">Missing evidence</p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-[12.5px] text-zinc-500">
            {ai!.missing_evidence!.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
