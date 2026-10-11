import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { refreshSession } from '../../api/auth'
import { vi } from '../../i18n/vi'

/** Landing page after Google SSO: the backend set the refresh cookie; exchange it for a session. */
export function AuthCallback() {
  const navigate = useNavigate()
  useEffect(() => {
    void refreshSession().then((ok) =>
      navigate(ok ? '/notes' : '/login?error=sso_failed', { replace: true }),
    )
  }, [navigate])
  return <p role="status">{vi.common.loading}</p>
}
