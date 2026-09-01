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

  return (
    <section className="space-y-4">
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
