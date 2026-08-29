import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { PageHeader } from './PageHeader'

const PAGE_TITLES: Record<string, string> = {
  '/reconciliations': 'Reconciliations',
  '/cases': 'Cases',
  '/transactions': 'Transactions',
  '/settings': 'Settings',
}

export function AppShell() {
  const { pathname } = useLocation()
  const isDashboard = pathname === '/dashboard' || pathname === '/'
  const caseDetail = pathname.startsWith('/cases/') && pathname !== '/cases'
  const pageTitle = caseDetail
    ? 'Case'
    : PAGE_TITLES[pathname] ?? null

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {!isDashboard && pageTitle && <PageHeader title={pageTitle} />}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

