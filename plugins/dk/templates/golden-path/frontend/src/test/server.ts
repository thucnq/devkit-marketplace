import { vi } from 'vitest'

type Route = { method?: string; path: string | RegExp; status?: number; body?: unknown }

/** Minimal fetch mock: tests describe the API, components stay untouched. */
export function mockApi(routes: Route[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = (init?.method ?? 'GET').toUpperCase()
    const route = routes.find(
      (r) =>
        (r.method ?? 'GET') === method &&
        (typeof r.path === 'string' ? url.startsWith(r.path) : r.path.test(url)),
    )
    if (!route)
      return new Response(JSON.stringify({ detail: `unmocked ${method} ${url}` }), { status: 500 })
    const status = route.status ?? 200
    return new Response(status === 204 ? null : JSON.stringify(route.body ?? {}), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
