import { useEffect, useState } from 'react'
import { api, ApiError, type MessageDraft, type MessageOption } from '../../lib/api'

/**
 * Draft an outbound message about a case — to the payment gateway, the
 * courier, or the customer.
 *
 * LEDGR NEVER SENDS. The model writes a draft grounded only in this case's
 * real facts, the user edits it, and their own mail client sends it. There is
 * no send endpoint on the backend either — a reconciliation tool must not
 * message a customer or a gateway about money on its own.
 */
type CaseDraftMessagePanelProps = {
  caseId: string
}

export function CaseDraftMessagePanel({ caseId }: CaseDraftMessagePanelProps) {
  const [options, setOptions] = useState<MessageOption[] | null>(null)
  const [active, setActive] = useState<MessageOption | null>(null)
  const [draft, setDraft] = useState<MessageDraft | null>(null)
  const [subject, setSubject] = useState('')
  const [bodyText, setBodyText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let cancelled = false
    setOptions(null)
    setActive(null)
    setDraft(null)
    setError(null)
    api
      .getMessageOptions(caseId)
      .then((r) => !cancelled && setOptions(r.options))
      .catch(() => !cancelled && setOptions([]))
    return () => {
      cancelled = true
    }
  }, [caseId])

  async function generate(option: MessageOption) {
    setBusy(true)
    setError(null)
    setActive(option)
    try {
      const d = await api.draftMessage(caseId, option.recipient_type)
      setDraft(d)
      setSubject(d.subject)
      setBodyText(d.body)
    } catch (err) {
      setDraft(null)
      if (err instanceof ApiError && err.status === 429) {
        setError('All AI providers are rate-limited right now. Try again shortly.')
      } else {
        setError(err instanceof Error ? err.message : 'Could not draft the message')
      }
    } finally {
      setBusy(false)
    }
  }

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(`Subject: ${subject}\n\n${bodyText}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Could not copy — select the text and copy manually.')
    }
  }

  // The recipient shown must come from the draft that actually returned, not
  // from whichever button was clicked last. Clicking a second recipient while
  // the first is still generating would otherwise show one recipient's address
  // above another recipient's message.
  const draftRecipient =
    draft && options
      ? options.find((o) => o.recipient_type === draft.recipient_type) ?? null
      : null

  const mailtoHref =
    `mailto:${encodeURIComponent(draftRecipient?.address ?? '')}` +
    `?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(bodyText)}`

  // Nothing sensible to contact about this case — don't show an empty panel.
  if (options !== null && options.length === 0) return null

  return (
    <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <h2 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">
        Draft a message
      </h2>
      <p className="mt-0.5 text-[12.5px] text-zinc-500 dark:text-zinc-400">
        AI writes a draft from this case's facts. You review, edit, and send it
        yourself — Ledgr never sends anything.
      </p>

      {options === null ? (
        <p className="mt-3 text-[13px] text-zinc-400">Loading…</p>
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          {options.map((o) => (
            <button
              key={o.recipient_type}
              type="button"
              disabled={busy}
              title={o.why}
              onClick={() => generate(o)}
              className={`rounded-lg border px-3 py-2 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                active?.recipient_type === o.recipient_type
                  ? 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-500/40 dark:bg-blue-500/10 dark:text-blue-300'
                  : 'border-zinc-200 text-zinc-700 hover:border-zinc-300 dark:border-zinc-700 dark:text-zinc-300'
              }`}
            >
              {busy && active?.recipient_type === o.recipient_type ? 'Drafting…' : o.label}
            </button>
          ))}
        </div>
      )}

      {error && <p className="mt-3 text-[12.5px] text-amber-700 dark:text-amber-500">{error}</p>}

      {draft && draftRecipient && (
        <div className="mt-4 space-y-3">
          {/* Honest about what we do and don't hold an address for. */}
          {draftRecipient.address ? (
            <p className="text-[12.5px] text-zinc-500 dark:text-zinc-400">
              To: <span className="font-medium text-zinc-800 dark:text-zinc-200">{draftRecipient.address}</span>
            </p>
          ) : (
            <p className="text-[12.5px] text-amber-700 dark:text-amber-500">{draftRecipient.note}</p>
          )}

          <div>
            <label className="mb-1 block text-[11.5px] font-medium uppercase tracking-wide text-zinc-400">
              Subject
            </label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-[13px] text-zinc-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:ring-blue-900/40"
            />
          </div>

          <div>
            <label className="mb-1 block text-[11.5px] font-medium uppercase tracking-wide text-zinc-400">
              Message — edit before sending
            </label>
            <textarea
              value={bodyText}
              onChange={(e) => setBodyText(e.target.value)}
              rows={10}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[13px] leading-relaxed text-zinc-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:ring-blue-900/40"
            />
          </div>

          {draft.facts_used.length > 0 && (
            <div className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-800/40">
              <p className="text-[11.5px] font-medium text-zinc-500 dark:text-zinc-400">
                Facts cited from this case
              </p>
              <ul className="mt-1 space-y-0.5">
                {draft.facts_used.map((f, i) => (
                  <li key={i} className="text-[12px] text-zinc-600 dark:text-zinc-400">
                    · {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={copyToClipboard}
              className="rounded-lg border border-zinc-200 px-3 py-2 text-[13px] font-medium text-zinc-700 transition-colors hover:border-zinc-300 dark:border-zinc-700 dark:text-zinc-300"
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
            <a
              href={mailtoHref}
              className="rounded-lg bg-blue-600 px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-blue-700"
            >
              Open in mail client
            </a>
            {draft.provider && (
              <span className="text-[11px] text-zinc-400 dark:text-zinc-500">
                Drafted by AI ({draft.provider})
              </span>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
