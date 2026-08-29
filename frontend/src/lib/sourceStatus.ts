import type { SourceStatus } from './api'

export type SourceDisplay = {
  label: string
  tone: 'connected' | 'demo' | 'error' | 'neutral'
}

export function sourceConnectionLabel(status: string): SourceDisplay {
  switch (status) {
    case 'connected_has_data':
    case 'connected_empty':
      return { label: 'Connected', tone: 'connected' }
    case 'mock_data':
    case 'demo_data':
      return { label: 'Demo data', tone: 'demo' }
    case 'auth_error':
    case 'api_error':
      return { label: 'Connection error', tone: 'error' }
    default:
      return { label: status.replace(/_/g, ' '), tone: 'neutral' }
  }
}

export function formatLastSync(iso: string | null): string {
  if (!iso) return 'Not synced yet'
  const at = new Date(iso)
  return at.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export type SourceRow = SourceStatus & {
  id: 'orders' | 'settlements' | 'bank'
  subtitle: string
}

export const SOURCE_ROWS: { id: SourceRow['id']; subtitle: string }[] = [
  { id: 'orders', subtitle: 'Order feed' },
  { id: 'settlements', subtitle: 'Settlement feed' },
  { id: 'bank', subtitle: 'COD remittance' },
]
