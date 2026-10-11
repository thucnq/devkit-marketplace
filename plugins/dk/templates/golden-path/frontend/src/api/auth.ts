import { ApiError } from './errors'

// Access token lives in memory only. The refresh token is an httpOnly cookie the JS never sees.
export type SessionUser = {
  id: string
  tenantId: string
  email: string
  fullName: string
  roles: string[]
}

type Session = { accessToken: string; user: SessionUser } | null

let session: Session = null
const listeners = new Set<() => void>()

export function getSession(): Session {
  return session
}

export function setSession(next: Session): void {
  session = next
  listeners.forEach((l) => l())
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

type TokenResponse = { accessToken: string; expiresIn: number; user: SessionUser }

let refreshing: Promise<boolean> | null = null

/** Exchanges the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= fetch('/api/auth/refresh', { method: 'POST', credentials: 'same-origin' })
    .then(async (res) => {
      if (!res.ok) {
        setSession(null)
        return false
      }
      const body = (await res.json()) as TokenResponse
      setSession({ accessToken: body.accessToken, user: body.user })
      return true
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    throw await ApiError.from(res)
  }
  const body = (await res.json()) as TokenResponse
  setSession({ accessToken: body.accessToken, user: body.user })
}

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }).catch(() => {})
  setSession(null)
}
