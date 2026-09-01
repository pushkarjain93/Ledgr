import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/layout/PageHeader'
import { api, type ReportData } from '../lib/api'
import { formatINR } from '../lib/money'
import { issueTypeLabel } from '../lib/caseUtils'
import { scrollAppMainToTop } from '../lib/scrollAppMain'

/**
 * Reports — the evidence page.
 *
 * Deliberately does NOT repeat the dashboard's throughput and work-split
 * numbers. It answers the one question nothing else in the product does:
 * how accurate is the reconciliation, measured against labelled data, and
 * what did it fail to resolve?
 *
 * Every figure is a count or ratio over records the engine actually
 * processed. Nothing is projected, estimated, or benchmarked against
 * anything we cannot show.
 *
 * LAYOUT INTENT: the whole report should be scannable in ~15 seconds. The
 * headline numbers are large and unadorned; every explanation, provider
 * breakdown and methodology note lives behind progressive disclosure. An
 * earlier version put all of it on screen at once and read as a technical
 * analytics dump rather than a financial report.
 */

// ---------------------------------------------------------------------------
// Shared primitives — matched to the Dashboard/Reconciliations design language
// (rounded-2xl, zinc-200 hairline, 18px semibold title, 13px muted subtitle).
// ---------------------------------------------------------------------------
function Card({
  title, subtitle, action, children, className = '',
}: {
  title?: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-700 dark:bg-zinc-900 lg:p-6 ${className}`}
    >
      {(title || action) && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h2 className="text-[18px] font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="mt-1 text-[13px] text-zinc-500 dark:text-zinc-400">{subtitle}</p>
            )}
          </div>
          {action}
        </div>
      )}
      <div className={title ? 'mt-6' : ''}>{children}</div>
    </section>
  )
}

/**
 * A collapsed disclosure. Uses native <details> so it is keyboard- and
 * screen-reader-correct with no state to manage.
 */
function Disclosure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg text-[13px] font-medium text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-zinc-50">
        <span>{label}</span>
        <svg
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="h-4 w-4 shrink-0 text-zinc-400 transition-transform group-open:rotate-180"
          aria-hidden
        >
          <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="mt-4">{children}</div>
    </details>
  )
}

function pct(v: number) {
  return `${(v * 100).toFixed(v === 1 ? 0 : 1)}%`
}

type Tone = 'good' | 'warn' | 'neutral'

const TONE_TEXT: Record<Tone, string> = {
  good: 'text-emerald-600 dark:text-emerald-400',
  warn: 'text-amber-600 dark:text-amber-400',
  neutral: 'text-zinc-900 dark:text-zinc-50',
}

/** A headline metric. Deliberately unboxed — nesting a bordered box inside a
 *  card was the single biggest source of visual noise on the old page. */
function Metric({
  label, value, note, tone = 'neutral', size = 'lg',
}: {
  label: string
  value: string
  note?: string
  tone?: Tone
  size?: 'lg' | 'md'
}) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
        {label}
      </p>
      <p
        className={`mt-2 font-semibold tabular-nums tracking-tight ${TONE_TEXT[tone]} ${
          size === 'lg' ? 'text-[34px] leading-none' : 'text-[24px] leading-none'
        }`}
      >
        {value}
      </p>
      {note && <p className="mt-2 text-[12.5px] text-zinc-500 dark:text-zinc-400">{note}</p>}
    </div>
  )
}

/** Two-segment donut. Sized in CSS pixels so it stays crisp at any zoom. */
function Donut({ correct, total }: { correct: number; total: number }) {
  const R = 52
  const C = 2 * Math.PI * R
  const share = total > 0 ? correct / total : 0
  return (
    <svg viewBox="0 0 140 140" className="h-[150px] w-[150px] shrink-0" role="img"
         aria-label={`${correct} of ${total} records settled by rules`}>
      <circle cx="70" cy="70" r={R} fill="none" strokeWidth="16"
              className="stroke-zinc-100 dark:stroke-zinc-800" />
      <circle
        cx="70" cy="70" r={R} fill="none" strokeWidth="16" strokeLinecap="round"
        className="stroke-emerald-500"
        strokeDasharray={`${C * share} ${C}`}
        transform="rotate(-90 70 70)"
      />
      <text x="70" y="66" textAnchor="middle"
            className="fill-zinc-900 text-[22px] font-semibold tabular-nums dark:fill-zinc-50">
        {total}
      </text>
      <text x="70" y="84" textAnchor="middle"
            className="fill-zinc-400 text-[10px] dark:fill-zinc-500">
        records
      </text>
    </svg>
  )
}

/** Stable colour per issue type, so a category keeps its colour between runs
 *  even as the ranking changes. */
const ISSUE_COLOR: Record<string, string> = {
  unmatched_order: 'bg-blue-500',
  unmatched_settlement: 'bg-emerald-500',
  ambiguous_match: 'bg-violet-500',
  remittance_overdue: 'bg-orange-500',
  partial_payment: 'bg-amber-500',
  overpayment: 'bg-teal-500',
  pending_settlement: 'bg-zinc-400',
}

function issueColor(caseType: string) {
  return ISSUE_COLOR[caseType] ?? 'bg-zinc-400'
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <>
      <PageHeader title="Reports" />
      <div className="mx-auto max-w-[1120px] px-6 py-8 lg:px-8 lg:py-10">{children}</div>
    </>
  )
}

export function ReportsPage() {
  const [data, setData] = useState<ReportData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .getReports()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : 'Failed to load'))
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return <Shell><p className="text-[14px] text-zinc-600 dark:text-zinc-400">{error}</p></Shell>
  }

  if (!data) {
    return <Shell><p className="text-[14px] text-zinc-500 dark:text-zinc-400">Loading…</p></Shell>
  }

  if (!data.has_data) {
    return (
      <Shell>
        <div className="rounded-2xl border border-zinc-200 bg-white p-10 text-center dark:border-zinc-700 dark:bg-zinc-900">
          <p className="text-[16px] font-semibold text-zinc-900 dark:text-zinc-50">
            Nothing to report yet
          </p>
          <p className="mx-auto mt-1.5 max-w-sm text-[13px] text-zinc-500 dark:text-zinc-400">
            Run a reconciliation and the performance report will appear here.
          </p>
          <Link
            to="/reconciliations"
            onClick={scrollAppMainToTop}
            className="mt-6 inline-block rounded-lg bg-blue-600 px-5 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-blue-700"
          >
            Go to Reconciliations
          </Link>
        </div>
      </Shell>
    )
  }

  const a = data.accuracy!
  const cov = data.coverage!
  const money = data.money!
  const ai = data.ai!
  const exceptions = data.exceptions ?? []
  // Outcome buckets, computed backend-side so this page and Reconciliations
  // partition the ledger identically. Falls back to an empty split if an older
  // response lacks it, rather than rendering NaN.
  const ws = data.work_split ?? {
    auto_settled: 0, awaiting_settlement: 0, ai_recommendation: 0,
    needs_investigation: 0, being_investigated: 0,
    total_records: a.total_records,
  }

  const exceptionTotal = exceptions.reduce((t, e) => t + e.amount_at_risk, 0)
  const exceptionCount = exceptions.reduce((t, e) => t + e.count, 0)
  const maxException = Math.max(...exceptions.map((e) => e.amount_at_risk), 1)

  const mismatchCount = a.records_scored - a.tier_correct
  const generated = data.generated_at
    ? new Date(data.generated_at).toLocaleString('en-IN', {
        day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit',
      })
    : null

  return (
    <>
      <PageHeader title="Reports" />
      <div className="mx-auto max-w-[1120px] px-6 py-8 lg:px-8 lg:py-10">
        {/* ---- page intro ---------------------------------------------- */}
        <div className="flex flex-wrap items-end justify-between gap-3">
          <p className="text-[14px] text-zinc-500 dark:text-zinc-400">
            Evaluate reconciliation performance and AI decision quality.
          </p>
          {generated && (
            <p className="text-[12.5px] text-zinc-400 dark:text-zinc-500">Generated {generated}</p>
          )}
        </div>

        <div className="mt-8 space-y-6">
          {/* ---- 1. headline: the numbers that decide whether to trust it ---- */}
          <Card
            title="Reconciliation performance"
            subtitle="Evaluation against the labelled demo dataset"
            action={
              <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-[11.5px] font-medium text-blue-700 dark:border-blue-500/25 dark:bg-blue-500/10 dark:text-blue-300">
                Demo evaluation · Synthetic labelled dataset
              </span>
            }
          >
            <div className="grid gap-8 sm:grid-cols-3">
              <Metric
                label="Clearing precision"
                value={pct(a.clearing_precision)}
                tone={a.false_clears === 0 ? 'good' : 'warn'}
                note={`${a.false_clears} false clears`}
              />
              <Metric
                label="Clearing recall"
                value={pct(a.clearing_recall)}
                tone={a.missed_clears === 0 ? 'good' : 'warn'}
                note={`${a.missed_clears} missed clears`}
              />
              <Metric
                label="Classification accuracy"
                value={pct(a.tier_accuracy)}
                tone={mismatchCount === 0 ? 'good' : 'neutral'}
                note={`${a.tier_correct} of ${a.records_scored} records`}
              />
            </div>

            <p className="mt-7 border-t border-zinc-100 pt-4 text-[12.5px] leading-relaxed text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
              These metrics evaluate Ledgr against known expected outcomes in the demo
              dataset. They are not production accuracy claims.
            </p>
          </Card>

          {/* ---- 2. classification quality + the actual mismatches ---------- */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Classification quality" subtitle="Correctness against ground truth">
              <p className="text-[40px] font-semibold leading-none tabular-nums tracking-tight text-zinc-900 dark:text-zinc-50">
                {pct(a.tier_accuracy)}
              </p>
              <p className="mt-2 text-[13px] text-zinc-500 dark:text-zinc-400">
                {a.tier_correct} / {a.records_scored} records classified correctly
              </p>

              <div className="mt-7 space-y-4">
                {[
                  { label: 'Correct', n: a.tier_correct, bar: 'bg-emerald-500' },
                  { label: 'Mismatch', n: mismatchCount, bar: 'bg-red-400' },
                ].map(({ label, n, bar }) => (
                  <div key={label}>
                    <div className="flex items-baseline justify-between gap-4">
                      <span className="text-[13px] text-zinc-600 dark:text-zinc-300">{label}</span>
                      <span className="text-[12.5px] tabular-nums text-zinc-500 dark:text-zinc-400">
                        {n} ({pct(a.records_scored ? n / a.records_scored : 0)})
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                      <div
                        className={`h-full rounded-full ${bar}`}
                        style={{ width: `${a.records_scored ? Math.max((n / a.records_scored) * 100, n > 0 ? 2 : 0) : 0}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* The other two graded dimensions stay available, but they are
                  almost always identical to tier accuracy — so they sit behind
                  a disclosure rather than tripling the numbers on screen. */}
              <div className="mt-7 border-t border-zinc-100 pt-4 dark:border-zinc-800">
                <Disclosure label="Other graded dimensions">
                  <dl className="space-y-3">
                    {[
                      ['Disposition', a.disposition_accuracy, a.disposition_correct],
                      ['Reason code', a.reason_accuracy, a.reason_correct],
                    ].map(([label, acc, correct]) => (
                      <div key={String(label)} className="flex items-baseline justify-between gap-4">
                        <dt className="text-[13px] text-zinc-600 dark:text-zinc-300">{label}</dt>
                        <dd className="text-[13px] tabular-nums text-zinc-900 dark:text-zinc-50">
                          <span className="font-semibold">{pct(Number(acc))}</span>{' '}
                          <span className="text-zinc-400 dark:text-zinc-500">
                            ({Number(correct)} of {a.records_scored})
                          </span>
                        </dd>
                      </div>
                    ))}
                  </dl>
                </Disclosure>
              </div>
            </Card>

            <Card
              title="Classification mismatches"
              subtitle={
                mismatchCount === 0
                  ? 'Every record matched ground truth'
                  : `${mismatchCount} record${mismatchCount === 1 ? '' : 's'} differed from ground truth`
              }
            >
              {a.misclassified.length === 0 ? (
                <div className="flex h-full min-h-[180px] flex-col items-center justify-center text-center">
                  <span className="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-50 dark:bg-emerald-500/10">
                    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75"
                         className="h-5 w-5 text-emerald-600 dark:text-emerald-400" aria-hidden>
                      <path d="M5 10.5l3.5 3.5L15 7" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                  <p className="mt-3 text-[13px] text-zinc-500 dark:text-zinc-400">
                    No mismatches in this evaluation.
                  </p>
                </div>
              ) : (
                <ul className="space-y-3">
                  {a.misclassified.map((m) => (
                    <li
                      key={m.record_id}
                      className="rounded-xl border border-zinc-200 bg-zinc-50/60 px-4 py-3 dark:border-zinc-700 dark:bg-zinc-800/40"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                        <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-50">
                          {m.record_id}
                        </span>
                        <div className="flex items-center gap-2 text-[11.5px]">
                          <span className="rounded-md bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                            {m.want_status}
                          </span>
                          <span className="text-zinc-400" aria-label="became">→</span>
                          <span className="rounded-md bg-red-50 px-2 py-0.5 font-medium text-red-700 dark:bg-red-500/10 dark:text-red-300">
                            {m.got_status}
                          </span>
                        </div>
                      </div>
                      <p className="mt-1.5 text-[11.5px] text-zinc-500 dark:text-zinc-400">
                        Expected tier {m.want_tier} · got tier {m.got_tier}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          {/* ---- 3. work split + money position ----------------------------- */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Who did the work" subtitle="How records were resolved">
              <div className="flex flex-wrap items-center gap-x-8 gap-y-6">
                <Donut correct={ws.auto_settled} total={ws.total_records} />
                <dl className="min-w-[190px] flex-1 space-y-4">
                  {[
                    { label: 'Auto matched', n: ws.auto_settled, dot: 'bg-emerald-500' },
                    { label: 'Awaiting settlement', n: ws.awaiting_settlement, dot: 'bg-zinc-400' },
                    { label: 'AI recommendation', n: ws.ai_recommendation, dot: 'bg-blue-500' },
                    { label: 'Needs investigation', n: ws.needs_investigation, dot: 'bg-orange-500' },
                    ...(ws.being_investigated > 0
                      ? [{ label: 'Being investigated', n: ws.being_investigated, dot: 'bg-violet-500' }]
                      : []),
                  ].map(({ label, n, dot }) => (
                    <div key={label} className="flex items-center justify-between gap-4">
                      <dt className="flex items-center gap-2.5 text-[13px] text-zinc-600 dark:text-zinc-300">
                        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} />
                        {label}
                      </dt>
                      <dd className="shrink-0 text-[13px] tabular-nums">
                        <span className="font-semibold text-zinc-900 dark:text-zinc-50">
                          {pct(n / Math.max(ws.total_records, 1))}
                        </span>{' '}
                        <span className="text-zinc-400 dark:text-zinc-500">({n})</span>
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>

              <p className="mt-7 border-t border-zinc-100 pt-4 text-[12.5px] leading-relaxed text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                Most records settle on rules alone, with no model involved. The same
                four buckets appear on Reconciliations, counted the same way.
              </p>
            </Card>

            <Card title="Where the money sits" subtitle="Across all reconciled records">
              <dl className="space-y-5">
                {[
                  { label: 'Expected', value: money.expected, tone: 'neutral' as Tone },
                  { label: 'Received', value: money.received, tone: 'neutral' as Tone },
                  { label: 'Still at risk', value: money.at_risk_open, tone: 'warn' as Tone },
                  { label: 'Resolved', value: money.recovered, tone: 'good' as Tone },
                ].map(({ label, value, tone }) => (
                  <div key={label} className="flex items-baseline justify-between gap-4">
                    <dt className="text-[13px] text-zinc-600 dark:text-zinc-300">{label}</dt>
                    <dd
                      className={`text-[19px] font-semibold tabular-nums tracking-tight ${
                        // Only the two figures that carry a judgement are coloured;
                        // colouring all four would flatten the hierarchy again.
                        value === 0 && tone === 'good' ? TONE_TEXT.neutral : TONE_TEXT[tone]
                      }`}
                    >
                      {formatINR(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </Card>
          </div>

          {/* ---- 4. the honest exception list + AI accountability ----------- */}
          <div className="grid gap-6 lg:grid-cols-3">
            <Card
              title="What could not be resolved"
              subtitle={`${exceptionCount} open cases · ${formatINR(exceptionTotal)} still at risk`}
              className="lg:col-span-2"
            >
              {exceptions.length === 0 ? (
                <p className="text-[13px] text-zinc-500 dark:text-zinc-400">
                  Everything reconciled. No open exceptions.
                </p>
              ) : (
                <>
                  <ul className="space-y-5">
                    {exceptions.map((e) => (
                      <li key={e.case_type}>
                        <div className="flex items-baseline justify-between gap-4">
                          <span className="text-[13px] text-zinc-700 dark:text-zinc-200">
                            {issueTypeLabel(e.case_type)}
                          </span>
                          <span className="shrink-0 text-[12.5px] tabular-nums text-zinc-500 dark:text-zinc-400">
                            {e.count} · {formatINR(e.amount_at_risk)}
                          </span>
                        </div>
                        {/* Bar width is share of the largest bucket — a relative
                            shape, not a claim about totals. */}
                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                          <div
                            className={`h-full rounded-full ${issueColor(e.case_type)}`}
                            style={{
                              width: `${Math.max((e.amount_at_risk / maxException) * 100, e.amount_at_risk > 0 ? 2 : 0)}%`,
                            }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                  <Link
                    to="/cases"
                    onClick={scrollAppMainToTop}
                    className="mt-7 inline-block text-[13px] font-medium text-blue-600 transition-colors hover:text-blue-700 dark:text-blue-400"
                  >
                    Review these cases →
                  </Link>
                </>
              )}
            </Card>

            <Card title="AI investigation" subtitle="How AI assisted with unresolved cases">
              <div className="space-y-7">
                <Metric label="Cases investigated" value={String(ai.cases_investigated)} size="md" />
                <Metric
                  label="Cases requiring retry"
                  value={String(ai.never_reached)}
                  tone={ai.never_reached > 0 ? 'warn' : 'neutral'}
                  size="md"
                />
                <Metric label="Cases per request" value={String(ai.model_batch_size)} size="md" />
              </div>

              <div className="mt-7 border-t border-zinc-100 pt-4 dark:border-zinc-800">
                <Disclosure label="How it works">
                  <div className="space-y-5">
                    <p className="text-[12.5px] leading-relaxed text-zinc-500 dark:text-zinc-400">
                      Cases are sent to the model in batches of {ai.model_batch_size} to limit API
                      calls. A case the model could not reach is marked retryable rather than
                      guessed at.
                    </p>

                    {Object.keys(ai.actions).length > 0 && (
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                          Recommendations made
                        </p>
                        <div className="mt-2.5 flex flex-wrap gap-2">
                          {Object.entries(ai.actions).map(([action, n]) => (
                            <span
                              key={action}
                              className="rounded-md bg-zinc-100 px-2.5 py-1 text-[12px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                            >
                              {action.replace(/_/g, ' ')}: <b>{n}</b>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {Object.keys(ai.providers).length > 0 && (
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                          Verdicts by provider
                        </p>
                        <div className="mt-2.5 flex flex-wrap gap-2">
                          {Object.entries(ai.providers).map(([p, n]) => (
                            <span
                              key={p}
                              className="rounded-md bg-zinc-100 px-2.5 py-1 text-[12px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                            >
                              {p}: <b>{n}</b>
                            </span>
                          ))}
                        </div>
                        <p className="mt-2.5 text-[12px] leading-relaxed text-zinc-500 dark:text-zinc-400">
                          Recorded per case because models calibrate differently — an
                          unattributed verdict cannot be audited.
                        </p>
                      </div>
                    )}
                  </div>
                </Disclosure>
              </div>
            </Card>
          </div>

          {/* ---- 5. method & limits: available, not shouted ----------------- */}
          <Card>
            <Disclosure label="Method & limitations">
              <ul className="space-y-3 text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-400">
                <li>
                  Accuracy is graded against <b>{cov.records_labelled}</b> labelled records.{' '}
                  {cov.records_unlabelled > 0 && (
                    <>
                      <b>{cov.records_unlabelled}</b> processed records have no ground-truth label
                      (settlement-side credits with no order behind them) and are excluded from the
                      accuracy figures rather than counted as correct.
                    </>
                  )}
                </li>
                <li>
                  Ground truth exists only for this synthetic dataset. These figures measure the
                  engine against known-correct answers; they are not a claim about live merchant
                  data.
                </li>
                <li>
                  The model classifies and explains. It never computes a financial value, and it
                  cannot clear money on its own — that is gated by deterministic rules on exposure.
                </li>
                <li>
                  “Who did the work” counts order-side <em>records</em>. The AI investigation
                  figures count <em>cases</em>, a different population — a case can also be raised
                  on the settlement side, where there is no order to grade.
                </li>
                <li>
                  No trends, forecasts, or comparisons appear here because the system holds no
                  historical time series to support them.
                </li>
              </ul>
            </Disclosure>
          </Card>

          <p className="pb-2 text-center text-[12px] text-zinc-400 dark:text-zinc-500">
            All amounts are in INR.
          </p>
        </div>
      </div>
    </>
  )
}
