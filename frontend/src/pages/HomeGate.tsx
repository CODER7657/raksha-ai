import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LandingPage } from './LandingPage'

/** "/" shows the public Landing page to logged-out visitors, and sends
 * already-authenticated users straight into the app instead of re-showing
 * marketing copy they've already acted on. */
export function HomeGate() {
  const { user, loading } = useAuth()

  if (loading) return null
  if (user) return <Navigate to="/app" replace />
  return <LandingPage />
}
