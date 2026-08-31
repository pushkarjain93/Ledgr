import { useNavigate } from 'react-router-dom'

type BellBatchPopoverProps = {
  onClose: () => void
}

export function BellBatchPopover({ onClose }: BellBatchPopoverProps) {
  const navigate = useNavigate()

  return (
    <div
      role="dialog"
      aria-labelledby="bell-batch-title"
      className="absolute right-0 top-[calc(100%+8px)] z-30 w-[272px] rounded-xl border border-zinc-200/80 bg-white/90 p-3.5 shadow-lg shadow-zinc-900/8 backdrop-blur-md dark:border-zinc-600 dark:bg-zinc-900/95 dark:shadow-black/40"
    >
      <div className="pointer-events-none absolute -top-1.5 right-3.5 h-3 w-3 rotate-45 border-l border-t border-zinc-200/80 bg-white/90 dark:border-zinc-600 dark:bg-zinc-900" />

      <div className="relative flex items-start gap-2.5">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-500/10">
          <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" stroke="currentColor" strokeWidth="1.5">
            <path d="M10 2.5a4.5 4.5 0 0 0-4.5 4.5v2.1L4 11.5h12l-1.5-2.4V7a4.5 4.5 0 0 0-4.5-4.5z" strokeLinejoin="round" />
            <path d="M8 14a2 2 0 0 0 4 0" strokeLinecap="round" />
          </svg>
        </span>
        <div className="min-w-0 flex-1">
          <p id="bell-batch-title" className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-50">
            New data arrived
          </p>
          <p className="mt-0.5 text-[12px] leading-snug text-zinc-600/90 dark:text-zinc-300">
            New orders and settlements are ready to reconcile.
          </p>
        </div>
        <button
          type="button"
          aria-label="Close notification panel"
          className="shrink-0 rounded-md p-0.5 text-zinc-400 transition-colors hover:bg-zinc-100/80 hover:text-zinc-600 dark:text-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
          onClick={onClose}
        >
          <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.5">
            <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="relative mt-3 flex gap-2">
        <button
          type="button"
          className="flex-1 rounded-lg bg-blue-600/95 px-3 py-2 text-[12.5px] font-medium text-white transition-colors hover:bg-blue-700"
          onClick={() => {
            onClose()
            navigate('/reconciliations')
          }}
        >
          Reconcile now
        </button>
        <button
          type="button"
          className="rounded-lg border border-zinc-200/90 bg-white/60 px-3 py-2 text-[12.5px] font-medium text-zinc-600 transition-colors hover:bg-white/90 dark:border-zinc-600 dark:bg-zinc-800/60 dark:text-zinc-200 dark:hover:bg-zinc-800"
          onClick={onClose}
        >
          Later
        </button>
      </div>
    </div>
  )
}

type BellEmptyPopoverProps = {
  onClose: () => void
}

export function BellEmptyPopover({ onClose }: BellEmptyPopoverProps) {
  return (
    <div
      role="dialog"
      className="absolute right-0 top-[calc(100%+8px)] z-30 w-[220px] rounded-xl border border-zinc-200/80 bg-white/90 p-3.5 shadow-lg shadow-zinc-900/8 backdrop-blur-md dark:border-zinc-600 dark:bg-zinc-900/95 dark:shadow-black/40"
    >
      <div className="pointer-events-none absolute -top-1.5 right-3.5 h-3 w-3 rotate-45 border-l border-t border-zinc-200/80 bg-white/90 dark:border-zinc-600 dark:bg-zinc-900" />
      <p className="relative text-[13px] font-medium text-zinc-800 dark:text-zinc-100">All caught up</p>
      <p className="relative mt-0.5 text-[12px] text-zinc-500 dark:text-zinc-400">Everything received so far has been reconciled.</p>
      <button
        type="button"
        className="relative mt-2.5 w-full rounded-lg border border-zinc-200/90 py-1.5 text-[12px] font-medium text-zinc-600 hover:bg-white/80 dark:border-zinc-600 dark:text-zinc-200 dark:hover:bg-zinc-800"
        onClick={onClose}
      >
        Close
      </button>
    </div>
  )
}
