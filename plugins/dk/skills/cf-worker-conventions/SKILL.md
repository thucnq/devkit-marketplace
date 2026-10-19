---
name: cf-worker-conventions
description: Conventions for Cloudflare Worker (TypeScript) + D1 + static web assets in a dk stack profile — routing, errors, D1 access, rate limiting, secrets, environments, frontend. Reference for /dk:design, /dk:build and /dk:review.
user-invocable: false
---

# Cloudflare Worker conventions (dk stack `kind = "ts-worker"` / `react-vite`)

## Worker
- One Worker serves `/api/*` (code) and everything else from static assets (`assets.run_worker_first: ["/api/*"]`, SPA fallback). Same origin as the web app ⇒ no CORS for it; any other origin is denied unless an ADR says otherwise.
- Routes in a small table (`src/index.ts`) or Hono if the project grows past ~15 routes (ADR). One module per feature under `src/features/<feature>/`.
- Errors are RFC 9457 `application/problem+json` via `problem()` (`src/http.ts`); never leak stack traces or SQL. Unknown `/api/*` → 404 problem.
- Validate every input (size, type, allowed values) before touching D1; reject unknown fields on writes.
- Write endpoints are rate limited (Workers rate limiting binding or a D1/KV counter keyed by a salted hash of IP + anonymous id — never store raw IPs longer than needed). Each gets an `AC-<FEAT>-ABUSE` test.
- Secrets (`ADMIN_TOKEN`, API keys) only from `env` (wrangler secrets); compare tokens in constant time; admin routes under `/api/admin/*` require it.

## D1 (SQLite)
- SQL only via `env.DB.prepare(sql).bind(...)`; batch related writes with `env.DB.batch([...])` (atomic). The eslint rule forbids template literals in `prepare`.
- Migrations: `npx wrangler d1 migrations create DB <slug>` → `NNNN_<slug>.sql`, expand-only (new tables/columns/indexes). Code must keep working on the previous schema during a deploy and after a code rollback.
- Ids `TEXT`, times `INTEGER` epoch ms UTC, JSON `TEXT CHECK (json_valid(...))`. Index every column the API filters or sorts on; paginate lists (max 100).

## Environments
- Top level of `wrangler.jsonc` = production; `env.staging` for agents. Agents never run `wrangler deploy|rollback|secret put|d1 … --remote` without `--env staging` (guard hook).
- `wrangler.jsonc` `database_id` values are not secrets; `.dev.vars` is (never read or commit it).

## Web (React + Vite)
- Plain fetch wrappers in `src/api.ts` typed from the OpenAPI contract; handle loading, error (`role="alert"`) and empty states; texts in Vietnamese.
- Mobile first (375 px), touch and mouse, `prefers-color-scheme` dark mode, no layout shift on load.
- Anything stored on the device (`localStorage`) is non-sensitive game/UI state only, wrapped in try/catch (private mode can throw).

## Tests
- Worker: `@cloudflare/vitest-plugin`, `SELF.fetch` integration tests against a D1 built from `migrations/`; titles start with the AC id.
- Web: Vitest + Testing Library + jsdom; stub `fetch`.
