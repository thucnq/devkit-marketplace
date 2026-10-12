# goldenpath

Freelance project built on the dk golden path. Docs and UI text in Vietnamese; code and identifiers in English.

## Workflow (dk plugin)
/dk:spec (đề xuất phạm vi) → chốt docs/scope.md → /dk:spec → /dk:approve spec → /dk:estimate → /dk:plan → /dk:design → /dk:approve contract → /dk:build <feature> → /dk:review → human merges → /dk:ship
Gates are enforced by hooks; state lives in `.dk/state.md` (edit only via dk-state.sh).

## Source of truth
- Requirements: `docs/brd.md`, `docs/acceptance/<feature>.md` (AC ids, one test each)
- Contract: `docs/api/openapi.yaml` · Schema: Flyway migrations (never edit committed ones) · ERD is generated
- Decisions: `docs/adr/`

## Commands
- Backend: `./mvnw -q -pl backend test -Dtest=<Class>` · full: `./mvnw -q verify` (needs Docker for Testcontainers)
- Frontend: `npm --prefix frontend run dev|typecheck|lint|test|build` · API types: `npm --prefix frontend run gen:api`
- Local DB: `docker compose -f deploy/compose.dev.yml up -d` · dev login: admin@demo.local / Demo@12345
- Debug API for the human's IDE: `bash scripts/dev/debug-api.sh` (JDWP :5005). Environment: WSL2 Ubuntu, repo under `~/` — see `docs/dev/wsl-intellij.md`; run `/dk:doctor` when tooling misbehaves.

## Non-negotiables
- Use platform building blocks: TenantEntity + RLS, AuditService/@Audited, @Pii + PiiEncryptedConverter, NotFoundException, PageRequests.
- Never read or write `deploy/envs/*.env` or `.env`; production is human-only.
- Never guess business rules (accounting, tax, legal): add the question to `docs/open-questions.md` and stop that part of the work.
- New Flyway migrations are named `V<yyyyMMddHHmm>__<slug>.sql` (UTC) so parallel branches never collide.
- Progress: `docs/plan/tien-do.md` is edited by humans (checkboxes, %); agents only regenerate it via `/dk:plan`.
- Fix the code, never the gate: quality configs (eslint, tsconfig, SpotBugs/PMD, gitleaks, CI workflows, ArchitectureTest, coverage thresholds) and suppressions (`@Disabled`, `NOPMD`, `@ts-ignore`, `eslint-disable`, `nosemgrep`, `.skip`) are blocked by the guard hook — stop and ask the human.
- Git hooks live in `.githooks/` (`git config core.hooksPath .githooks`); never bypass them.
- Build evidence: RED before implementing, GREEN after (`dk-evidence.py`, `.dk/evidence/<feature>.json` is committed).
