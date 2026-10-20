---
name: design
description: Produce the technical design from an approved spec — Flyway schema, OpenAPI contract, Mermaid system/sequence diagrams, and ADRs for non-obvious decisions.
argument-hint: "[feature-slug to (re)design only one feature]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

## Gate
!`bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" require spec 2>&1`

## Existing design
!`ls backend/src/main/resources/db/migration/ docs/adr/ docs/diagrams/ 2>/dev/null || true`

Scope: $ARGUMENTS (empty = all features in the BRD)

## Stack
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk_stack.py" info 2>/dev/null || echo "stack: java-spring"`

With a stack profile whose migration kind is `wrangler-seq` (Cloudflare D1, SQLite), step 1 differs: new file `cd worker && npx wrangler d1 migrations create DB <slug>` (name `NNNN_<slug>.sql`, numbers strictly increase - `check-migrations.sh --kind wrangler-seq`); ids `TEXT` (UUIDv7 or a stable natural key), instants `INTEGER` epoch milliseconds UTC, booleans `INTEGER` 0/1, JSON as `TEXT` with a `CHECK (json_valid(col))`; no RLS in SQLite - isolation (if any) is a WHERE clause tested by an AC; indexes for every lookup the API does; expand-only rules are the same. Draw `docs/db/erd.md` by hand as a small Mermaid `erDiagram` (do not regenerate it), then `gen-erd.sh --check` must report 0 drift. Read `${CLAUDE_PLUGIN_ROOT}/skills/cf-worker-conventions/SKILL.md` instead of the Spring parts of the security baseline.

## Task
Read `docs/brd.md`, `docs/acceptance/*.md`, and `${CLAUDE_PLUGIN_ROOT}/skills/security-baseline/SKILL.md`. Then:

1. **Schema** — new Flyway file(s) `backend/src/main/resources/db/migration/V<yyyyMMddHHmm>__<slug>.sql` (UTC timestamp: `date -u +%Y%m%d%H%M`). Never edit an already-committed migration. Expand-only: add tables/nullable columns/indexes; no DROP/RENAME/type change/SET NOT NULL on existing columns (`check-migrations.sh` fails them unless the file has `-- dk:allow-destructive <reason>`).
   - Every tenant-owned table: `tenant_id uuid not null`, RLS enabled with the policy from the security baseline, index leading with `tenant_id`.
   - Ids `uuid` (generated in app, UUIDv7), money `numeric(19,2)`, instants `timestamptz`, `created_at/updated_at/created_by/updated_by`, optimistic lock `version int`.
   - Sensitive PII columns are `bytea` (encrypted) + optional `<col>_hash bytea` for exact-match lookup.
   - Write the ERD afterwards with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/gen-erd.sh"` — don't draw it by hand.
2. **Contract** — update `docs/api/openapi.yaml` (OpenAPI 3.1). Every operation: `operationId`, `security`, all error responses using the shared `Problem` schema (RFC 9457), pagination on lists (`page`, `size`, max 100). Add the AC IDs an operation serves in `x-ac: [AC-ORDER-01, ...]`. Validate: `npx -y @redocly/cli@1 lint docs/api/openapi.yaml`.
3. **Diagrams** — `docs/diagrams/system.mmd` (C4-container level, keep to one screen) and `docs/diagrams/seq-<flow>.mmd` only for flows with ≥3 actors or async steps.
4. **ADRs** — `docs/adr/NNNN-<slug>.md` (Bối cảnh / Quyết định / Hệ quả / Phương án đã loại) only for decisions a future maintainer would question: deviating from the golden path, adding infrastructure, choosing a library, storing sensitive data.
5. Default to the golden path. Adding Kafka, Redis, a second database, or any paid service needs an ADR proving the BRD's numbers require it — low-load freelance projects almost never do.

## Finish
- Commit `design: <summary>`; set `contract: draft` via `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" set contract draft`.
- Reply in Vietnamese, max 10 lines: tables added, endpoints added, ADRs written, anything in the spec that the design could not satisfy. End with: "Duyệt bằng `/dk:approve contract`."
