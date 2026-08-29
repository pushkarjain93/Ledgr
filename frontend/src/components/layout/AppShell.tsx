import { useLayoutEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { SidebarProvider } from '../../context/SidebarContext'
import { scrollAppMainToTop } from '../../lib/scrollAppMain'
import { Sidebar } from './Sidebar'
import { PageHeader } from './PageHeader'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/reconciliations': 'Reconciliations',
  '/cases': 'Cases',
  '/transactions': 'Transactions',
  '/settings': 'Settings',
}

export function AppShell() {
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  const isDashboard = location.pathname === '/dashboard' || location.pathname === '/'
  const caseDetail = location.pathname.startsWith('/cases/') && location.pathname !== '/cases'
  const pageTitle = caseDetail
    ? 'Case'
    : PAGE_TITLES[location.pathname] ?? null

  useLayoutEffect(() => {
    scrollAppMainToTop()
    if (mainRef.current) mainRef.current.scrollTop = 0
  }, [location.pathname, location.search, location.key])

  return (
    <SidebarProvider>
      <div className="flex h-screen overflow-hidden bg-zinc-50 dark:bg-[#0a0a0c]">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {pageTitle && (
            <PageHeader
              title={pageTitle}
              variant={isDashboard ? 'dashboard' : 'default'}
            />
          )}
          <main ref={mainRef} data-app-main className="min-h-0 flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  )
}

