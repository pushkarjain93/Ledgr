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
      <SummaryBoxes model={model} />

      <div className="grid gap-4 lg:grid-cols-2">
        <FinancialHealthPanel model={model} />
        <ReconciliationOutcomePanel
          segments={model.outcome}
          total={model.totals.totalRecords}
        />
      </div>

      <CodAwaitingSettlementPanel cases={codAwaiting} />

      <AiReviewQueue cases={cases} reviewCount={model.aiReviewCount} />
    </section>
  )
}
