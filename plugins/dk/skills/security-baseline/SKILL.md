---
name: security-baseline
description: Security, multi-tenancy, PII and audit rules for golden-path projects. Use when designing tables/endpoints or touching auth, tenant data, personal data, or audit.
user-invocable: false
---

# Security baseline (golden path)

The golden path already implements everything below. Use the building blocks; never write a parallel mechanism.

## Authentication
- Password login `POST /api/auth/login` and Google SSO (`/oauth2/authorization/google`) both end the same way: `TokenService` issues a 15-min HS256 access JWT (claims `sub`=userId, `tid`=tenantId, `roles`) returned in the body, and a 7-day refresh token set as cookie `rt` (`HttpOnly; Secure; SameSite=Strict; Path=/api/auth`).
- Refresh tokens are stored hashed (`refresh_token.token_hash`), rotated on every use; presenting a revoked token revokes the whole family (reuse detection).
- Google SSO never auto-creates users: the verified Google email must match an existing, active `app_user`. Tenants invite users.
- `LoginRateLimiter`: 5 failures / 15 min per (IP, email) → 429.
- Frontend keeps the access token in memory only. Never localStorage.

## Authorization
- Every endpoint: `@PreAuthorize("hasRole('X')")` or explicitly listed in `SecurityConfig.PUBLIC_PATHS`. Default is deny.
- Never trust tenant, user id, or role from the request body/query. They come from `CurrentUser` (JWT).

## Multi-tenancy - Postgres Row-Level Security
- `TenantFilter` copies `tid` from the JWT into `TenantContext`; `TenantAwareDataSource` runs `set_config('app.tenant_id', <tid>, false)` on every connection checkout and clears it on return.
- The app connects as role `app_rw` (NOT owner, NOT superuser) so RLS applies. Flyway runs as the owner.
- Every tenant-owned table:
  ```sql
  tenant_id uuid not null,
  ...
  alter table x enable row level security;
  alter table x force row level security;
  create policy tenant_isolation on x
    using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    with check (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
  create index on x (tenant_id, <most common filter>);
  -- grants: default privileges from V1 give app_rw select/insert/update/delete on new tables
  ```
- Insert: set `tenant_id` from `TenantContext.require()` in the entity's `@PrePersist` (extend `TenantEntity`).
- Jobs outside a request: wrap the work in `TenantContext.runAs(tenantId, () -> ...)` per tenant. No tenant set → RLS returns zero rows (fails safe).
- Cross-tenant lookups of a resource return 404, never 403.
- Fail-closed endpoint catalog (from hopnhat): one test enumerates every mapped endpoint (`RequestMappingHandlerMapping`) and fails if any endpoint is not classified (public / authenticated / tenant-scoped with the owning path variable); for tenant-scoped ones it calls the endpoint as a user of another tenant and asserts nothing of the target tenant leaks (status, body markers such as names and tax codes). A new endpoint without a classification breaks the build instead of silently shipping unchecked.

## Personal data (PII)
- Annotate personal fields with `@Pii`. `PiiMasker` masks them in logs, audit details and `toString()` (records: implement `toString()` via `PiiMasker.describe(this)`).
- Sensitive data (see `vn-data-protection`) is stored encrypted: `@Convert(converter = PiiEncryptedConverter.class)` on a `bytea` column (AES-256-GCM, key `APP_PII_KEY`, random 96-bit IV per value). For exact-match search add a `<col>_hash` column filled by `PiiCrypto.get().hash(value)` (HMAC-SHA256 of the normalised value, key `APP_PII_HASH_KEY`).
- Files containing sensitive data (scans, biometric images): store encrypted at rest (`EncryptedFileStore`), never in a public bucket, never in logs, delete raw inputs once processed unless the BRD's retention says otherwise.
- Never log request bodies. Never put PII in URLs, metric labels, or exception messages.

## Audit
- `AuditService.record(action, entityType, entityId, details)` or annotate the service method with `@Audited(action = "NOTE_UPDATE", entity = "note")`. Runs in the caller's transaction - if the business change rolls back, so does its audit row.
- Audit every state change on business entities, every login/logout/failed login, every role change, and every READ of sensitive personal data.
- `audit_event` is range-partitioned by month; `AuditMaintenanceJob` calls the `audit_maintain(retention_months)` SECURITY DEFINER function daily (creates next partitions, drops expired). Retention: `app.audit.retention-months` (default 3).
- `details` is JSON produced by `PiiMasker` - it never contains raw PII.

## Input & output
- Bean Validation on every request DTO (`@Valid`), with size limits on every string and collection.
- Errors are RFC 9457 `application/problem+json` from `GlobalExceptionHandler`; no stack traces, no SQL, no internal ids of other tenants.
- File uploads: check size, magic bytes (not the extension), and re-encode images server-side before processing.

## Secrets
- Only via environment variables (`deploy/envs/*.env`, never committed - gitleaks + the plugin's hook block it). `deploy/.env.example` lists every variable with a dummy value.
