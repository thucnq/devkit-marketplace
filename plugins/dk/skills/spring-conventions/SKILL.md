---
name: spring-conventions
description: Backend conventions for golden-path projects (Java 21, Spring Boot 3, JPA, Flyway, Testcontainers). Use when writing or changing backend code or tests.
user-invocable: false
paths:
  - "backend/**"
---

# Backend conventions

## Layout — package by feature
```
<base>.platform.*        shared building blocks (security, tenant, audit, pii, web, id) — change rarely
<base>.feature.<name>    one package per feature: <Name>Controller, <Name>Service, <Name>Repository, <Name> (entity), dto/
```
ArchUnit (`ArchitectureTest`) enforces: controllers → services → repositories only; features never import another feature's repository or entity (call its service); `platform` never imports `feature`.

## Code
- DTOs are Java records with Bean Validation; entities never leave the service layer.
- Entities: extend `TenantEntity` (tenant-owned) or `BaseEntity`; ids `UUID` from `Ids.newId()` (UUIDv7); `@Version` for optimistic locking.
- Money `BigDecimal` + `numeric(19,2)`; instants `Instant` + `timestamptz`; dates the user picks `LocalDate`.
- Services own transactions (`@Transactional` on public methods; `readOnly = true` for queries).
- Lists are paginated: `Pageable` with max size 100 (`PageRequests.of(page, size, sort)`), response `PageResponse<T>`.
- Not found → `throw new NotFoundException("note", id)` → 404 problem+json.
- No Lombok. Records and plain constructors.
- Logging: SLF4J with placeholders; never log DTOs or entities that contain `@Pii` fields except via `PiiMasker.describe(obj)`.
- Config via `@ConfigurationProperties` records under `app.*`, documented in `deploy/.env.example`.

## Database
- Flyway `V<yyyyMMddHHmm>__<slug>.sql` (UTC timestamp, `out-of-order: true`) so parallel branches never collide; never edit a committed migration; expand-only (see `check-migrations.sh`).
- Tenant tables follow the RLS template in `security-baseline`. Grants to `app_rw` come from the default privileges set in V1 — no per-table grant needed.
- Prefer one well-chosen index per real query; explain-analyze anything that scans > 10k rows.

## Testing
- Acceptance tests: extend `ApiTestBase` (Testcontainers Postgres 17, MockMvc, helpers `newTenant()`, `newUser(tenant, roles)`, `bearer(user)`, `json(...)`, `auditCount(tenant, action, id)`). One `@Test` per AC id, `@DisplayName("AC-XXX-NN: ...")`.
- Unit tests only for non-trivial pure logic (calculations, parsers, state machines). Don't unit-test getters or Spring wiring.
- Test data via builders in `src/test/java/.../fixtures`, never shared mutable SQL dumps.
- Run a single class: `./mvnw -q -pl backend test -Dtest=NoteApiTest`. Full suite: `./mvnw -q verify`.
