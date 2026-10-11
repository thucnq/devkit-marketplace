// NFR smoke test (thresholds = docs/brd.md §7). Run: k6 run -e BASE_URL=https://staging.example.vn deploy/k6/smoke.js
// Optional authenticated reads: -e EMAIL=... -e PASSWORD=...  (use a staging-only account)
import http from 'k6/http'
import { check, sleep } from 'k6'

const BASE = __ENV.BASE_URL
export const options = {
  vus: 20,
  duration: '30s',
  thresholds: {
    'http_req_failed': ['rate<0.01'],
    'http_req_duration{kind:read}': ['p(95)<300'],
    'http_req_duration{kind:health}': ['p(95)<200'],
  },
}

export function setup() {
  if (!__ENV.EMAIL) return { token: null }
  const res = http.post(`${BASE}/api/auth/login`, JSON.stringify({ email: __ENV.EMAIL, password: __ENV.PASSWORD }), {
    headers: { 'Content-Type': 'application/json' },
  })
  check(res, { 'login 200': (r) => r.status === 200 })
  return { token: res.json('accessToken') }
}

export default function (data) {
  const h = http.get(`${BASE}/api/actuator/health`, { tags: { kind: 'health' } })
  check(h, { 'health UP': (r) => r.status === 200 })
  if (data.token) {
    const r = http.get(`${BASE}/api/notes?size=20`, { headers: { Authorization: `Bearer ${data.token}` }, tags: { kind: 'read' } })
    check(r, { 'list 200': (x) => x.status === 200 })
  }
  sleep(1)
}
