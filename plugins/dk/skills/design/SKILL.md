---
name: design
description: Produce the technical design from an approved spec — Flyway schema, OpenAPI contract, Mermaid system/sequence diagrams, and ADRs for non-obvious decisions.
argument-hint: "[feature-slug to (re)design only one feature]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

## Gate
!`bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" require spec`

## Existing design
!`ls backend/src/main/resources/db/migration/ docs/adr/ docs/diagrams/ 2>/dev/null || true`

Scope: $ARGUMENTS (empty = all features in the BRD)

## Task
Read `docs/brd.md`, `docs/acceptance/*.md`, and `${CLAUDE_PLUGIN_ROOT}/skills/security-baseline/SKILL.md`. Then:

1. **Schema** — new Flyway file(s) `backend/src/main/resources/db/migration/V<next>__<slug>.sql`. Never edit an already-committed migration.
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
