import { isAwaitingSettlementCase, isOpenForReview, needsHumanDecision } from './caseUtils'
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
      list = list.filter(needsHumanDecision)
    } else if (filter === 'ai_pending') {
      list = list.filter((c) => c.case_status === 'ai_pending')
    }
  }

  // Highest AI confidence first: this is the AI REVIEW queue, so the cases
  // the model is most certain about come first and can be cleared quickly.
  // Cases with no score yet (ai_pending, or never investigated) sink to the
  // bottom rather than sorting as 0 — "not scored" is not the same claim as
  // "scored zero". Ties fall back to amount_at_risk, so among equally
  // confident cases the most financially exposed is still surfaced first.
  return list.sort((a, b) => {
    const ac = a.ai?.confidence
    const bc = b.ai?.confidence
    const aScored = ac !== null && ac !== undefined
    const bScored = bc !== null && bc !== undefined
    if (aScored !== bScored) return aScored ? -1 : 1
    if (aScored && bScored && ac !== bc) return bc - ac
    return b.amount_at_risk - a.amount_at_risk
  })
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
