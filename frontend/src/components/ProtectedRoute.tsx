import { Navigate, Outlet } from 'react-router-dom'
import { useApp } from '../context/AppContext'

export function ProtectedRoute() {
  const { merchant } = useApp()
  if (!merchant) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
