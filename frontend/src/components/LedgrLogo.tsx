type LedgrLogoProps = {
  size?: 'sm' | 'md'
  showWordmark?: boolean
}

export function LedgrLogo({ size = 'md', showWordmark = true }: LedgrLogoProps) {
  const markSize = size === 'sm' ? 28 : 32
  const wordSize = size === 'sm' ? 'text-[15px]' : 'text-[17px]'

  return (
    <div className="flex items-center gap-2.5">
      <svg
        width={markSize}
        height={markSize}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        className="shrink-0"
      >
        <rect width="32" height="32" rx="8" fill="#dbeafe" />
        <path d="M9 10h8M9 16h11M9 22h6" stroke="#1d4ed8" strokeWidth="1.75" strokeLinecap="round" />
        <path d="M22 10v12" stroke="#3b82f6" strokeWidth="1.75" strokeLinecap="round" />
        <circle cx="22" cy="16" r="2" fill="#60a5fa" />
      </svg>
      {showWordmark && (
        <span
          className={`${wordSize} font-semibold tracking-[-0.03em] text-ledgr-ink`}
        >
          Ledgr
        </span>
      )}
    </div>
  )
}
