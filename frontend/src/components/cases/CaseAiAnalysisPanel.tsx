import { confidenceTier } from '../../lib/caseDisplay'
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
  const ai = caseItem.ai
  const tier = confidenceTier(ai?.confidence)
  const finding = ai?.reason?.trim() || caseItem.explanation || 'No AI finding available yet.'
  const recommendation = ai?.next_step?.trim() || '—'
  const evidence = ai?.evidence ?? []

  return (
    <section
      id="case-ai-analysis"
      className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">AI Analysis</h2>
        {ai?.confidence !== null && ai?.confidence !== undefined && (
          <span className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${tier.badgeClass}`}>
            {ai.confidence}% Confidence · {tier.label}
          </span>
        )}
      </div>

      {ai?.error && (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200">
          {ai.error}
        </p>
      )}

      <div className="mt-4">
        <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">Finding</p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-700 dark:text-zinc-300">{finding}</p>
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
          {recommendation}
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
