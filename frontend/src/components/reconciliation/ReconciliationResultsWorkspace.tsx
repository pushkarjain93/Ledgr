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

  // Two genuinely different in-progress states, not one. `needsAi` means AI
  // hasn't reached a case yet -- the split below is not known, so showing a
  // number (even 0) claims a fact nobody has established. `pending` means AI
  // ran out of room to keep trying right now (a rate limit) -- waiting
  // longer buys nothing, so there is no reason to keep hiding what IS known.
  const needsAiCount = cases.filter((c) => c.case_status === 'needs_ai').length
  const pendingCount = cases.filter((c) => c.case_status === 'ai_pending').length

  // Hide the numbers only while every open case is still genuinely being
  // worked and nothing has hit a wall yet. The moment either condition ends
  // -- the batch clears, or AI gets stuck -- keep hiding buys nothing, so
  // show what's actually known instead of a "0" that looks final but isn't.
  const awaitingFirstVerdict = needsAiCount > 0 && pendingCount === 0

  return (
    <section className="space-y-4">
      {awaitingFirstVerdict ? (
        <div className="flex flex-wrap items-center gap-2.5 rounded-xl border border-blue-200 bg-blue-50/70 px-4 py-3 dark:border-blue-500/25 dark:bg-blue-500/10">
          <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
          <p className="text-[13px] text-blue-900 dark:text-blue-200">
            AI is investigating {needsAiCount} case{needsAiCount === 1 ? '' : 's'} — the
            figures below will appear once this completes.
          </p>
        </div>
      ) : pendingCount > 0 ? (
        <div className="flex flex-wrap items-center gap-2.5 rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3 dark:border-amber-500/25 dark:bg-amber-500/10">
          <span className="h-2 w-2 rounded-full bg-amber-500" />
          <p className="text-[13px] text-amber-900 dark:text-amber-200">
            AI hit a rate limit on {pendingCount} case{pendingCount === 1 ? '' : 's'} and
            paused. Showing what's confirmed so far — retry the pending case
            {pendingCount === 1 ? '' : 's'} from the queue below when ready.
          </p>
        </div>
      ) : null}

      <SummaryBoxes model={model} cases={cases} pending={awaitingFirstVerdict} />

      <div className="grid gap-4 lg:grid-cols-2">
        <FinancialHealthPanel model={model} pending={awaitingFirstVerdict} />
        {/* Denominator is the sum of the segments themselves, so the centre
            number always equals what the ring depicts. Using the per-run
            record count instead made the segments (cumulative, case-derived)
            add up to something other than the total shown. */}
        <ReconciliationOutcomePanel
          segments={model.outcome}
          total={model.outcome.reduce((n, s) => n + s.count, 0)}
          pending={awaitingFirstVerdict}
        />
      </div>

      <CodAwaitingSettlementPanel cases={codAwaiting} />

      <AiReviewQueue cases={cases} />
    </section>
  )
}
