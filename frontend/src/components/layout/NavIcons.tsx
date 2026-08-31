type IconProps = {
  className?: string
}

const base = 'h-[18px] w-[18px] shrink-0'

export function NavIconDashboard({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <rect x="3.5" y="3.5" width="5.5" height="5.5" rx="1.25" />
      <rect x="11" y="3.5" width="5.5" height="5.5" rx="1.25" />
      <rect x="3.5" y="11" width="5.5" height="5.5" rx="1.25" />
      <rect x="11" y="11" width="5.5" height="5.5" rx="1.25" />
    </svg>
  )
}

export function NavIconReconciliations({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M6.5 4.5L3.5 7.5l3 3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3.5 7.5h8a3 3 0 0 1 3 3v0.5" strokeLinecap="round" />
      <path d="M13.5 15.5l3-3-3-3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M16.5 12.5H8.5a3 3 0 0 1-3-3v-0.5" strokeLinecap="round" />
    </svg>
  )
}

export function NavIconCases({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M6.5 3.5h7l2 2v11a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1z" strokeLinejoin="round" />
      <path d="M13.5 3.5V6h2.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7 10h6M7 13h4" strokeLinecap="round" />
    </svg>
  )
}

export function NavIconTransactions({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <rect x="3" y="5" width="14" height="10" rx="2" />
      <path d="M3 9h14" strokeLinecap="round" />
      <path d="M7 13h3" strokeLinecap="round" />
    </svg>
  )
}

export function NavIconReports({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <rect x="3.5" y="3.5" width="13" height="13" rx="2" />
      <path d="M7 13V9.5M10 13V7M13 13v-2.5" strokeLinecap="round" />
    </svg>
  )
}

export function NavIconSettings({ className = base }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

export function NavIconHelp({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path
        d="M4 5.5a6 6 0 0 1 12 0v5l-2 2H6l-2-2v-5z"
        strokeLinejoin="round"
      />
      <path d="M8 13.5h4" strokeLinecap="round" />
    </svg>
  )
}
