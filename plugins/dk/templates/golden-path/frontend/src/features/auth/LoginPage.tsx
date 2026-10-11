import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { login } from '../../api/auth'
import { ApiError } from '../../api/errors'
import { vi } from '../../i18n/vi'

export function LoginPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const ssoError = params.get('error')
  const [error, setError] = useState<string | null>(
    ssoError === 'sso_not_invited' ? vi.login.ssoNotInvited : ssoError ? vi.login.ssoFailed : null,
  )

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setPending(true)
    setError(null)
    try {
      await login(email, password)
      navigate('/notes', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="narrow">
      <h1>{vi.login.title}</h1>
      <form onSubmit={onSubmit}>
        <label>
          {vi.login.email}
          <input
            type="email"
            autoComplete="username"
            required
            maxLength={320}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          {vi.login.password}
          <input
            type="password"
            autoComplete="current-password"
            required
            maxLength={200}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={pending}>
          {vi.login.submit}
        </button>
      </form>
      <a className="button secondary" href="/oauth2/authorization/google">
        {vi.login.google}
      </a>
    </main>
  )
}
