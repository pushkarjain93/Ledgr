import { Navigate, Outlet } from 'react-router-dom'
import { useApp } from '../context/AppContext'

export function ProtectedRoute() {
  const { merchant, loading } = useApp()

  // Session restore is async. Without this guard, a hard load of any route
  // (refresh, deep link, back/forward) renders with merchant still null,
  // redirects to /login with `replace`, and destroys the requested URL —
  // so the user lands on /dashboard instead of the page they asked for.
  if (loading) return null

  if (!merchant) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
