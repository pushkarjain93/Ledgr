import {
  aiReachedVerdict,
  hasWorkingNote,
  isAwaitingSettlementCase,
  isOpenForReview,
  needsInvestigation,
} from './caseUtils'
import type { Case } from '../types/case'

export function awaitingSettlementCases(cases: Case[]): Case[] {
  return cases
    .filter((c) => isAwaitingSettlementCase(c))
    .sort((a, b) => {
      const ageA = a.order_date || a.created_at
      const ageB = b.order_date || b.created_at
      return ageA.localeCompare(ageB)
    })
}

export function filterCases(cases: Case[], filter: string | null): Case[] {
  let list = [...cases]

  if (filter === 'resolved') {
    list = list.filter((c) => c.resolution?.resolved)
  } else if (filter === 'bookmarked') {
    list = list.filter((c) => c.bookmarked)
  } else if (filter === 'pending_settlement') {
    list = list.filter((c) => isAwaitingSettlementCase(c))
  } else {
    list = list.filter((c) => isOpenForReview(c))
    if (filter === 'needs_decision') {
      list = list.filter(aiReachedVerdict)
    } else if (filter === 'has_notes') {
      list = list.filter(hasWorkingNote)
    } else if (filter === 'needs_investigation') {
      // No dedicated "waiting on AI" filter any more: a case AI has not
      // reached yet is a transient state, not a workload category, and it
      // still appears under All open.
      list = list.filter(needsInvestigation)
    }
  }

  // Highest money at risk first. Confidence was tried as the sort key and
  // removed: measured on this project's own data it carried almost no signal
  // (83% of cases came back at exactly 10, and evidence count did not
  // correlate with it). Exposure is a real, deterministic number, and "work
  // the biggest loss first" is what a finance team actually does.
  return list.sort((a, b) => b.amount_at_risk - a.amount_at_risk)
}

export function caseQueuePath(filter: string | null): string {
  return filter ? `/cases?filter=${filter}` : '/cases'
}

export function caseNeighbors(
  queue: Case[],
  caseId: string,
): { prev: Case | null; next: Case | null; position: number; total: number } {
  const index = queue.findIndex((c) => c.case_id === caseId)
  if (index === -1) {
    return { prev: null, next: null, position: -1, total: queue.length }
  }
  return {
    prev: index > 0 ? queue[index - 1]! : null,
    next: index < queue.length - 1 ? queue[index + 1]! : null,
    position: index + 1,
    total: queue.length,
  }
}

export function caseDetailPath(caseId: string, filter: string | null): string {
  return filter ? `/cases/${caseId}?filter=${filter}` : `/cases/${caseId}`
}
