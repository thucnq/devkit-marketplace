# goldenpath

Freelance project built on the dk golden path. Docs and UI text in Vietnamese; code and identifiers in English.

## Workflow (dk plugin)
/dk:spec (đề xuất phạm vi) → chốt docs/scope.md → /dk:spec → /dk:approve spec → /dk:estimate → /dk:design → /dk:approve contract → /dk:build <feature> → /dk:review → human merges → /dk:ship
Gates are enforced by hooks; state lives in `.dk/state.md` (edit only via dk-state.sh).

## Source of truth
- Requirements: `docs/brd.md`, `docs/acceptance/<feature>.md` (AC ids, one test each)
- Contract: `docs/api/openapi.yaml` · Schema: Flyway migrations (never edit committed ones) · ERD is generated
- Decisions: `docs/adr/`

## Commands
- Backend: `./mvnw -q -pl backend test -Dtest=<Class>` · full: `./mvnw -q verify` (needs Docker for Testcontainers)
- Frontend: `npm --prefix frontend run dev|typecheck|lint|test|build` · API types: `npm --prefix frontend run gen:api`
- Local DB: `docker compose -f deploy/compose.dev.yml up -d` · dev login: admin@demo.local / Demo@12345

## Non-negotiables
- Use platform building blocks: TenantEntity + RLS, AuditService/@Audited, @Pii + PiiEncryptedConverter, NotFoundException, PageRequests.
- Never read or write `deploy/envs/*.env` or `.env`; production is human-only.
