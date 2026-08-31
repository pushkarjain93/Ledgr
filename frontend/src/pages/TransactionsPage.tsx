import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BackToCaseLink } from '../components/BackToCaseLink'
import { TransactionDetailDrawer } from '../components/transactions/TransactionDetailDrawer'
import { TransactionFiltersBar } from '../components/transactions/TransactionFilters'
import { TransactionsTable } from '../components/transactions/TransactionsTable'
import { useApp } from '../context/AppContext'
import { api, type TransactionRecord } from '../lib/api'
import {
  filterTransactions,
  hasActiveTransactionFilters,
  type TransactionFilters,
  uniquePaymentModes,
} from '../lib/transactionDisplay'

const DEFAULT_FILTERS: TransactionFilters = {
  search: '',
  date: '',
  paymentMode: 'all',
  status: 'all',
}

export function TransactionsPage() {
  const { allRuns, cases } = useApp()
  // ?search=ORD-00024 — how AI cross-links land here from a case's reasoning.
  const [searchParams] = useSearchParams()
  const initialSearch = searchParams.get('search') ?? ''
  const [records, setRecords] = useState<TransactionRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [filters, setFilters] = useState<TransactionFilters>({
    ...DEFAULT_FILTERS,
    search: initialSearch,
  })
  const [selected, setSelected] = useState<TransactionRecord | null>(null)

  const loadTransactions = useCallback(async () => {
    if (allRuns.length === 0) {
      setRecords([])
      setLoading(false)
      return
    }

    setLoading(true)
    setLoadError(null)
    try {
      const res = await api.getTransactions()
      setRecords(res.records)
    } catch {
      setRecords([])
      setLoadError('Could not load transactions. Try syncing again from Reconciliations.')
    } finally {
      setLoading(false)
    }
  }, [allRuns.length])

  useEffect(() => {
    loadTransactions()
  }, [loadTransactions])

  const casesById = useMemo(
    () => new Map(cases.map((caseItem) => [caseItem.case_id, caseItem])),
    [cases],
  )

  const paymentModes = useMemo(() => uniquePaymentModes(records), [records])

  const filtered = useMemo(
    () => filterTransactions(records, filters),
    [records, filters],
  )

  const hasRuns = allRuns.length > 0

  return (
    <div className="mx-auto max-w-[1120px] px-6 py-8 lg:px-8 lg:py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <BackToCaseLink />
        <h1 className="text-[22px] font-semibold text-zinc-900 dark:text-zinc-50">Transactions</h1>
          <p className="mt-1.5 max-w-xl text-[14px] text-zinc-500 dark:text-zinc-400">
            Search reconciled orders and settlements — including auto-matched records.
          </p>
        </div>
        {hasRuns && !loading && (
          <p className="text-[13px] tabular-nums text-zinc-500 dark:text-zinc-400">
            {filtered.length} of {records.length} records
          </p>
        )}
      </div>

      {!hasRuns ? (
        <div className="mt-8 rounded-2xl border border-dashed border-zinc-200 bg-zinc-50 px-6 py-14 text-center dark:border-zinc-700 dark:bg-zinc-800/40">
          <p className="text-[15px] font-medium text-zinc-800 dark:text-zinc-100">
            No transactions yet
          </p>
          <p className="mt-1.5 text-[13px] text-zinc-500 dark:text-zinc-400">
            Run Sync &amp; Reconcile first — every matched and exception record will appear here.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          <TransactionFiltersBar
            filters={filters}
            paymentModes={paymentModes}
            onChange={setFilters}
          />

          <section className="overflow-hidden rounded-2xl border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900">
            {loading ? (
              <p className="px-5 py-14 text-center text-[13px] text-zinc-400">Loading transactions…</p>
            ) : loadError ? (
              <p className="px-5 py-14 text-center text-[13px] text-red-600 dark:text-red-400">
                {loadError}
              </p>
            ) : (
              <TransactionsTable
                records={filtered}
                selectedId={selected?.record_id ?? null}
                onSelect={setSelected}
                emptyMessage={
                  hasActiveTransactionFilters(filters)
                    ? 'No records match these filters.'
                    : 'No transaction records returned.'
                }
              />
            )}
          </section>
        </div>
      )}

      {selected && (
        <TransactionDetailDrawer
          record={selected}
          casesById={casesById}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
