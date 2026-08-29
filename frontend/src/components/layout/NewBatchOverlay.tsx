import { useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'

type NewBatchOverlayProps = {
  open: boolean
  hasBatch: boolean
  onClose: () => void
}

export function NewBatchOverlay({ open, hasBatch, onClose }: NewBatchOverlayProps) {
  const { state, dismissNotification } = useApp()
  const navigate = useNavigate()

  if (!open) return null

  if (!hasBatch || !state) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-start justify-center bg-black/20 px-4 pt-24 backdrop-blur-[2px]"
        role="dialog"
        aria-modal="true"
        onClick={onClose}
      >
        <div
          className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <h2 className="text-[17px] font-semibold text-zinc-900">No new batches</h2>
          <p className="mt-2 text-[14px] text-zinc-500">
            You&apos;re all caught up. New order or settlement batches will appear here.
          </p>
          <button
            type="button"
            className="mt-5 w-full rounded-lg border border-zinc-200 py-2.5 text-[14px] font-medium text-zinc-600 hover:bg-zinc-50"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    )
  }

  const batchNum = state.notification_batch ?? state.current_batch

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/20 px-4 pt-24 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-batch-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-blue-50">
          <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5 text-blue-600" stroke="currentColor" strokeWidth="1.5">
            <path d="M10 2.5a4.5 4.5 0 0 0-4.5 4.5v2.1L4 11.5h12l-1.5-2.4V7a4.5 4.5 0 0 0-4.5-4.5z" strokeLinejoin="round" />
            <path d="M8 14a2 2 0 0 0 4 0" strokeLinecap="round" />
          </svg>
        </div>

        <h2 id="new-batch-title" className="text-[17px] font-semibold text-zinc-900">
          New batch arrived
        </h2>
        <p className="mt-2 text-[14px] leading-relaxed text-zinc-500">
          Batch {batchNum} has new orders and settlements ready to reconcile.
        </p>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-blue-700"
            onClick={() => {
              dismissNotification()
              onClose()
              navigate('/reconciliations')
            }}
          >
            Reconcile now
          </button>
          <button
            type="button"
            className="flex-1 rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-[14px] font-medium text-zinc-600 transition-colors hover:bg-zinc-50"
            onClick={() => {
              dismissNotification()
              onClose()
            }}
          >
            Ignore
          </button>
        </div>
      </div>
    </div>
  )
}
