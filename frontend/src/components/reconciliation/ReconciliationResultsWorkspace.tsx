import type { Case } from '../../types/case'
import type { ReconciliationViewModel } from '../../lib/reconciliationFinancials'
import { awaitingSettlementCases } from '../../lib/caseQueue'
import { AiReviewQueue } from './AiReviewQueue'
import { CodAwaitingSettlementPanel } from './CodAwaitingSettlementPanel'
import { FinancialHealthPanel } from './FinancialHealthPanel'
import { ReconciliationOutcomePanel } from './ReconciliationOutcomePanel'
import { SummaryBoxes } from './ReconciliationSummary'

type ReconciliationResultsWorkspaceProps = {
  model: ReconciliationViewModel
  cases: Case[]
}

export function ReconciliationResultsWorkspace({ model, cases }: ReconciliationResultsWorkspaceProps) {
  const codAwaiting = awaitingSettlementCases(cases)
  // Cases AI has not reached yet. While any remain, these figures are a
  // snapshot mid-investigation, not the batch's final result -- say so rather
  // than letting a partial chart read as finished.
  const investigating = cases.filter(
    (c) => !c.resolution?.resolved &&
      (c.case_status === 'needs_ai' || c.case_status === 'ai_pending'),
  ).length

  return (
    <section className="space-y-4">
      {investigating > 0 && (
        <div className="flex flex-wrap items-center gap-2.5 rounded-xl border border-blue-200 bg-blue-50/70 px-4 py-3 dark:border-blue-500/25 dark:bg-blue-500/10">
          <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
          <p className="text-[13px] text-blue-900 dark:text-blue-200">
            AI is investigating {investigating} more case{investigating === 1 ? '' : 's'} —
            these figures update as verdicts arrive, and are final once this clears.
          </p>
        </div>
      )}
      <SummaryBoxes model={model} cases={cases} />

      <div className="grid gap-4 lg:grid-cols-2">
        <FinancialHealthPanel model={model} />
        {/* Denominator is the sum of the segments themselves, so the centre
            number always equals what the ring depicts. Using the per-run
            record count instead made the segments (cumulative, case-derived)
            add up to something other than the total shown. */}
        <ReconciliationOutcomePanel
          segments={model.outcome}
          total={model.outcome.reduce((n, s) => n + s.count, 0)}
        />
      </div>

      <CodAwaitingSettlementPanel cases={codAwaiting} />

      <AiReviewQueue cases={cases} />
    </section>
  )
}
