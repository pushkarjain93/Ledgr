type IconProps = {
  className?: string
}

export function MailIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <rect x="2.5" y="4.5" width="15" height="11" rx="1.5" />
      <path d="M3 6.5l7 5 7-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function LockIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <rect x="4.5" y="9" width="11" height="8.5" rx="1.5" />
      <path
        d="M7 9V6.5a3 3 0 0 1 6 0V9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="13" r="1" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function EyeIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d="M2.5 10s2.75-5 7.5-5 7.5 5 7.5 5-2.75 5-7.5 5-7.5-5-7.5-5z" />
      <circle cx="10" cy="10" r="2.25" />
    </svg>
  )
}

export function EyeOffIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d="M3 3l14 14" strokeLinecap="round" />
      <path d="M7.2 7.6A4.2 4.2 0 0 0 10 14.5c1.6 0 3-.9 3.8-2.2M5.8 5.9C3.9 7.1 2.5 10 2.5 10s2.75 5 7.5 5c1.1 0 2.1-.2 3-.6" />
    </svg>
  )
}

export function ArrowRightIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d="M4 10h11" strokeLinecap="round" />
      <path d="M12 6.5L15.5 10 12 13.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
