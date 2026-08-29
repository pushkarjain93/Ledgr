import { NavLink } from 'react-router-dom'
import { LedgrLogo } from '../LedgrLogo'
import { useApp } from '../../context/AppContext'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/reconciliations', label: 'Reconciliations' },
  { to: '/cases', label: 'Cases' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/settings', label: 'Settings' },
] as const

function HelpIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4">
      <circle cx="10" cy="10" r="7.5" />
      <path d="M8 8a2 2 0 1 1 3.2 1.6c-.8.5-1.2 1-1.2 2.4" strokeLinecap="round" />
      <circle cx="10" cy="14.5" r="0.75" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function Sidebar() {
  const { merchant } = useApp()

  return (
    <aside className="flex h-full w-[240px] shrink-0 flex-col border-r border-zinc-200 bg-white">
      <div className="px-5 pt-6 pb-5">
        <LedgrLogo size="sm" />
        {merchant && (
          <p className="mt-3 truncate text-[12px] font-medium text-zinc-500">
            {merchant.company_name}
          </p>
        )}
      </div>

      <nav className="flex-1 px-3">
        <ul className="space-y-0.5">
          {NAV_ITEMS.map(({ to, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `block rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900'
                  }`
                }
              >
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t border-zinc-200 px-3 py-4">
        <a
          href="mailto:support@ledgr.ai"
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
        >
          <HelpIcon />
          Help
        </a>
      </div>
    </aside>
  )
}
