import { getSession, refreshSession } from './auth'
import { ApiError } from './errors'

/** fetch wrapper: bearer token, one transparent refresh on 401, problem+json → ApiError. */
export async function api<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getSession()?.accessToken
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  const res = await fetch(path, { ...init, headers, credentials: 'same-origin' })
  if (res.status === 401 && !retried && (await refreshSession())) {
    return api<T>(path, init, true)
  }
  if (!res.ok) throw await ApiError.from(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
