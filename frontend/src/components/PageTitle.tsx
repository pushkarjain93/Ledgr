import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * Keeps the browser tab title in step with the current route.
 *
 * `index.html` can only carry one static title, so every screen inherited
 * "Ledgr — Sign in" — including long after signing in. That is wrong on any
 * page, and it is the label that shows up in a screen recording, a bookmark,
 * and the browser's own tab strip when several screens are open at once.
 *
 * Renders nothing; it exists purely for the side effect.
 */
const TITLES: Record<string, string> = {
  '/login': 'Sign in',
  '/dashboard': 'Dashboard',
  '/reconciliations': 'Reconciliations',
  '/cases': 'Cases',
  '/transactions': 'Transactions',
  '/reports': 'Reports',
  '/settings': 'Settings',
}

export function PageTitle() {
  const { pathname } = useLocation()

  useEffect(() => {
    // Read the case id off the path rather than with useParams: this component
    // sits above <Routes> so no route has matched for it, and useParams would
    // always come back empty here.
    const caseMatch = pathname.match(/^\/cases\/(.+)$/)
    // A case ticket is the one screen where the specific record matters more
    // than the section name -- with several open, "Cases" on every tab tells
    // you nothing about which case you are looking at.
    const label = caseMatch
      ? decodeURIComponent(caseMatch[1]).replace(/^CASE-/, '')
      : TITLES[pathname]
    document.title = label ? `Ledgr — ${label}` : 'Ledgr'
  }, [pathname])

  return null
}
