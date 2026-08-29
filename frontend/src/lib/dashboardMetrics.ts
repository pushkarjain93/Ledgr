import { isOpenForReview, needsHumanDecision } from './caseUtils'
import type { MerchantState } from '../types/case'

export type DashboardMetrics = {
  needsDecisionCount: number
}

export function listCases(state: MerchantState) {
  return Object.values(state.cases)
}

export function computeDashboardMetrics(state: MerchantState): DashboardMetrics {
  const openCases = listCases(state).filter((c) => isOpenForReview(c))
  return {
    needsDecisionCount: openCases.filter(needsHumanDecision).length,
  }
}
