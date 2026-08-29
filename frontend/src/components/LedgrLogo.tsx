type LedgrLogoProps = {
  size?: 'sm' | 'md'
  showWordmark?: boolean
}

/** Minimal ledger mark — book spine + entry lines. */
function LedgrMark({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <rect width="32" height="32" rx="7" fill="#2563eb" />
      <path
        d="M11 8.5v15"
        stroke="white"
        strokeWidth="2.25"
        strokeLinecap="round"
      />
      <path
        d="M15 12.5h12M15 17h9M15 21.5h11"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeOpacity="0.92"
      />
    </svg>
  )
}

export function LedgrLogo({ size = 'md', showWordmark = true }: LedgrLogoProps) {
  const markSize = size === 'sm' ? 28 : 32
  const wordSize = size === 'sm' ? 'text-[15px]' : 'text-[17px]'

  return (
    <div className="flex items-center gap-2.5">
      <LedgrMark size={markSize} />
      {showWordmark && (
        <span className={`${wordSize} font-semibold tracking-[-0.03em] text-ledgr-ink dark:text-zinc-50`}>
          Ledgr
        </span>
      )}
    </div>
  )
}

export function LedgrMarkIcon({ size = 32 }: { size?: number }) {
  return <LedgrMark size={size} />
}
