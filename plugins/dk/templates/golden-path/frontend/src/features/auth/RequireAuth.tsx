import { useEffect, useState, type ReactNode } from 'react'
import { Navigate } from 'react-router'
import { refreshSession } from '../../api/auth'
import { vi } from '../../i18n/vi'
import { useSession } from './useSession'

/** On a fresh page load the access token is gone; try the refresh cookie once before redirecting. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const session = useSession()
  const [checked, setChecked] = useState(session !== null)

  useEffect(() => {
    if (!checked) {
      void refreshSession().finally(() => setChecked(true))
    }
  }, [checked])

  if (session) return <>{children}</>
  if (!checked) return <p role="status">{vi.common.loading}</p>
  return <Navigate to="/login" replace />
}
