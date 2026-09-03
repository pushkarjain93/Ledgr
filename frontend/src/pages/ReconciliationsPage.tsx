import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ReconciliationResultsWorkspace } from '../components/reconciliation/ReconciliationResultsWorkspace'
import { RunHistoryTable } from '../components/reconciliation/RunHistoryTable'
import { useApp } from '../context/AppContext'
import { scrollAppMainToTop } from '../lib/scrollAppMain'
import { formatLastSync } from '../components/reconciliation/SourceCards'
import { api, ApiError, type SyncResult, type TransactionRecord } from '../lib/api'
import { buildReconciliationViewModel } from '../lib/reconciliationFinancials'
import { parseRun } from '../lib/reconciliationMetrics'

function SyncIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 10h12M12 6l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function syncStatusMessage(
  totalBatches: number,
  currentBatch: number,
  batchAvailable: boolean,
  nextBatchAvailableAt: string | null,
): { eyebrow: string; title: string; detail: string; tone: 'ready' | 'waiting' | 'done' } {
  if (currentBatch > totalBatches) {
    return {
      eyebrow: 'All caught up',
      title: 'All new data reconciled',
      detail: 'Every order and settlement on file has been processed. Reset demo data from your profile menu to run through the flow again.',
      tone: 'done',
    }
  }

  if (batchAvailable) {
    return {
      eyebrow: 'New data available',
      title: 'New data has arrived',
      detail: 'Fresh orders and settlements are ready. Run Sync & Reconcile to match records and investigate exceptions.',
      tone: 'ready',
    }
  }

  if (nextBatchAvailableAt) {
    return {
      eyebrow: 'Up to date',
      title: 'No new data to reconcile',
      // Deliberately no predicted arrival time: in production nobody knows
      // when the next orders or settlements land, and promising a clock time
      // we cannot honour reads as a bug the moment it slips.
      detail: 'Everything received so far has been reconciled. New orders and settlements appear here automatically as they arrive.',
      tone: 'waiting',
    }
  }

  return {
    eyebrow: 'No new data',
    title: 'Nothing to reconcile right now',
    detail: 'Your sources are up to date. New orders and settlements will appear here when they arrive.',
    tone: 'waiting',
  }
}

export function ReconciliationsPage() {
  const {
    refresh,
    allRuns,
    batchAvailable,
    currentBatch,
    nextBatchAvailableAt,
    totalBatches,
    lastSyncAt,
    ordersProcessed,
    // The live, already-polled case list -- AppContext refreshes this every
    // 4s while any case is still `needs_ai`. This page used to keep its own
    // separate copy fetched once right after sync, which meant the KPI
    // cards / financial health / outcome donut below stayed frozen at
    // whatever AI had (not) concluded the instant sync finished, while the
    // "AI is investigating" banner -- reading this same context value --
    // correctly ticked down. Using the context copy directly is what makes
    // the two agree, and is a precondition for the pending-dash gate below:
    // there is no point hiding numbers behind "-" if the number underneath
    // is itself never going to update.
    cases,
  } = useApp()

  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [syncNotice, setSyncNotice] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<SyncResult | null>(null)

  const [transactions, setTransactions] = useState<TransactionRecord[]>([])

  const viewModel = useMemo(() => {
    if (allRuns.length === 0 || transactions.length === 0) return null
    return buildReconciliationViewModel(allRuns, transactions, cases, ordersProcessed)
  }, [allRuns, transactions, cases, ordersProcessed])

  const loadResultsData = useCallback(async () => {
    if (allRuns.length === 0) {
      setTransactions([])
      return
    }
    try {
      const tx = await api.getTransactions()
      setTransactions(tx.records)
    } catch {
      setTransactions([])
    }
  }, [allRuns.length])

  useEffect(() => {
    loadResultsData()
  }, [loadResultsData, allRuns.length])

  const status = syncStatusMessage(
    totalBatches,
    currentBatch,
    batchAvailable,
    nextBatchAvailableAt,
  )

  const hasNewDataToSync = batchAvailable && currentBatch <= totalBatches
  const latestRunPoint = lastResult ? parseRun(lastResult.run, lastResult.run.batch_id) : null

  async function handleSync() {
    if (syncing) return

    setSyncError(null)
    setSyncNotice(null)
    setLastResult(null)

    if (!hasNewDataToSync) {
      if (currentBatch > totalBatches) {
        setSyncNotice(
          'All available data has been reconciled. There is nothing new to sync right now.',
        )
      } else if (nextBatchAvailableAt) {
        setSyncNotice(
          'No new data to sync. Everything received so far has been reconciled.',
        )
      } else {
        setSyncNotice('No new data to sync. Your sources are already up to date.')
      }
      return
    }

    setSyncing(true)
    try {
      const result = await api.syncAndReconcile()
      setLastResult(result)
      await refresh()
      await loadResultsData()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setSyncNotice('No new data to sync. Your sources are already up to date.')
      } else {
        setSyncError(err instanceof ApiError ? err.message : 'Sync failed')
      }
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1120px] space-y-6 px-6 py-8 lg:px-8 lg:py-10">
      <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-700 dark:bg-zinc-900 lg:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 max-w-xl">
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
              {status.eyebrow}
            </p>
            <h2 className="mt-1 text-[18px] font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
              {status.title}
            </h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500 dark:text-zinc-400">
              {status.detail}
            </p>
            {lastSyncAt && (
              <p className="mt-2 text-[12px] text-zinc-400 dark:text-zinc-500">
                Last sync: {formatLastSync(lastSyncAt)}
              </p>
            )}
          </div>

          <button
            type="button"
            disabled={syncing}
            onClick={handleSync}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {syncing ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Syncing…
              </>
            ) : (
              <>
                <SyncIcon />
                Sync &amp; Reconcile
              </>
            )}
          </button>
        </div>

        {syncNotice && (
          <p className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50 px-3.5 py-2.5 text-[13px] text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-200">
            {syncNotice}
          </p>
        )}

        {syncError && (
          <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-[13px] text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200">
            {syncError}
          </p>
        )}

        {status.tone === 'waiting' && nextBatchAvailableAt && !batchAvailable && (
          <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-[13px] text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200">
            This page updates automatically when new orders or settlements arrive.
          </p>
        )}

        {latestRunPoint && (
          <p className="mt-4 text-[12px] text-emerald-700 dark:text-emerald-400">
            Reconciliation complete —{' '}
            <Link to="/cases" onClick={scrollAppMainToTop} className="font-medium underline-offset-2 hover:underline">
              review cases
            </Link>
          </p>
        )}
      </section>

      {viewModel && viewModel.totals.totalRecords > 0 && (
        <ReconciliationResultsWorkspace model={viewModel} cases={cases} />
      )}

      <RunHistoryTable runs={allRuns} />
    </div>
  )
}
