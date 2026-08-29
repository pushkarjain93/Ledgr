type CaseDocumentsPanelProps = {
  onNavigate: (sectionId: string) => void
}

const LINKS = [
  { id: 'case-summary', label: 'Order Details' },
  { id: 'case-summary', label: 'Settlement Details' },
  { id: 'case-ai-analysis', label: 'Fee Structure (MDR)' },
  { id: 'case-timeline', label: 'Activity Log' },
] as const

export function CaseDocumentsPanel({ onNavigate }: CaseDocumentsPanelProps) {
  return (
    <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">Supporting Documents</h2>
      <ul className="mt-4 space-y-2">
        {LINKS.map(({ id, label }) => (
          <li key={label}>
            <button
              type="button"
              onClick={() => onNavigate(id)}
              className="text-[13px] font-medium text-blue-600 hover:underline dark:text-blue-400"
            >
              {label}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
