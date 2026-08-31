import { NavLink } from 'react-router-dom'
import type { KeyboardEvent, ComponentType } from 'react'
import { LedgrLogo, LedgrMarkIcon } from '../LedgrLogo'
import { useApp } from '../../context/AppContext'
import { useSidebar } from '../../context/SidebarContext'
import {
  NavIconCases,
  NavIconDashboard,
  NavIconHelp,
  NavIconReconciliations,
  NavIconReports,
  NavIconSettings,
  NavIconTransactions,
} from './NavIcons'

type NavIconComponent = ComponentType<{ className?: string }>

const NAV_ITEMS: { to: string; label: string; Icon: NavIconComponent }[] = [
  { to: '/dashboard', label: 'Dashboard', Icon: NavIconDashboard },
  { to: '/reconciliations', label: 'Reconciliations', Icon: NavIconReconciliations },
  { to: '/cases', label: 'Cases', Icon: NavIconCases },
  { to: '/transactions', label: 'Transactions', Icon: NavIconTransactions },
  { to: '/reports', label: 'Reports', Icon: NavIconReports },
  { to: '/settings', label: 'Settings', Icon: NavIconSettings },
]

function SidebarCollapseIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4 shrink-0"
      aria-hidden
    >
      <rect x="3.5" y="4.5" width="4" height="11" rx="1" />
      <path d="M10.5 10H7M9 8L7 10l2 2" />
    </svg>
  )
}

function SidebarCollapseButton({ onToggle }: { onToggle: () => void }) {
  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onToggle()
    }
  }

  return (
    <button
      type="button"
      onClick={onToggle}
      onKeyDown={onKeyDown}
      aria-label="Collapse sidebar"
      title="Collapse sidebar"
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-200 text-zinc-500 transition-colors hover:border-zinc-300 hover:bg-zinc-50 hover:text-zinc-800 dark:border-zinc-600 dark:text-zinc-400 dark:hover:border-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
    >
      <SidebarCollapseIcon />
    </button>
  )
}

function SidebarExpandButton({ onToggle }: { onToggle: () => void }) {
  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onToggle()
    }
  }

  return (
    <button
      type="button"
      onClick={onToggle}
      onKeyDown={onKeyDown}
      aria-label="Expand sidebar"
      title="Expand sidebar"
      className="flex h-10 w-10 items-center justify-center rounded-lg transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800"
    >
      <LedgrMarkIcon size={28} />
    </button>
  )
}

export function Sidebar() {
  const { merchant } = useApp()
  const { collapsed, toggleCollapsed } = useSidebar()

  return (
    <aside
      className={`flex h-full shrink-0 flex-col border-r border-zinc-200 bg-white transition-[width] duration-200 ease-out dark:border-zinc-700 dark:bg-zinc-900 ${
        collapsed ? 'w-[72px]' : 'w-[240px]'
      }`}
    >
      <div className={`pt-5 pb-2 ${collapsed ? 'px-2' : 'px-3'}`}>
        {collapsed ? (
          <div className="flex justify-center">
            <SidebarExpandButton onToggle={toggleCollapsed} />
          </div>
        ) : (
          <div className="px-2">
            <div className="flex items-start justify-between gap-2">
              <LedgrLogo size="sm" showWordmark />
              <SidebarCollapseButton onToggle={toggleCollapsed} />
            </div>
            {merchant?.company_name && (
              <p className="mt-2 truncate text-[12px] font-medium text-zinc-500 dark:text-zinc-400">
                {merchant.company_name}
              </p>
            )}
          </div>
        )}
      </div>

      <nav className={`flex-1 ${collapsed ? 'px-2' : 'px-3'}`}>
        <ul className="space-y-1">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  `flex items-center rounded-lg text-[13.5px] font-medium transition-colors ${
                    collapsed ? 'justify-center px-0 py-2.5' : 'gap-3 px-3 py-2'
                  } ${
                    isActive
                      ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'
                      : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50'
                  }`
                }
              >
                <Icon />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className={`border-t border-zinc-200 dark:border-zinc-700 ${collapsed ? 'px-2 py-3' : 'px-3 py-4'}`}>
        <a
          href="mailto:support@ledgr.ai"
          title={collapsed ? 'Help' : undefined}
          className={`flex items-center rounded-lg text-[13px] font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50 ${
            collapsed ? 'justify-center py-2.5' : 'gap-3 px-3 py-2'
          }`}
        >
          <NavIconHelp />
          {!collapsed && <span>Help</span>}
        </a>
      </div>
    </aside>
  )
}
