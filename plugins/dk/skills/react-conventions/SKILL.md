---
name: react-conventions
description: Frontend conventions for golden-path projects (React 19, TypeScript, Vite, TanStack Query, Capacitor for mobile). Use when writing or changing frontend code or tests.
user-invocable: false
paths:
  - "frontend/**"
---

# Frontend conventions

## Layout
```
src/api/        client.ts (fetch wrapper: access token in memory, auto-refresh on 401, problem+json → ApiError), generated types
src/features/<name>/   pages, components, hooks (use<Name>Query / use<Name>Mutation)
src/components/        shared UI only
src/i18n/vi.ts         all user-facing strings (Vietnamese); no hard-coded text in components
```

## Rules
- Types for API payloads are generated from the contract: `npm run gen:api` (openapi-typescript → `src/api/schema.d.ts`). Never hand-write a type that exists in the contract.
- Server state only through TanStack Query; no global store for server data. Local UI state with `useState`.
- Access token lives in memory (`src/api/auth.ts`); refresh token is the httpOnly cookie. Never use localStorage/sessionStorage for tokens or PII.
- Every data view handles 4 states: loading, error (show `ApiError.detail`), empty, data.
- Forms: controlled inputs + validation mirroring the backend limits; disable submit while pending (prevents double submit).
- Mobile: the same build is wrapped by Capacitor (`npm run cap:sync`). Avoid browser-only APIs without a fallback; use `@capacitor/*` plugins behind a small adapter in `src/platform/`.
- Styling: plain CSS modules; keep it boring and accessible (labels on inputs, focus states, contrast).

## Testing
- Vitest + Testing Library; mock at the fetch layer (`src/test/server.ts`). Test behaviour from the user's view (`getByRole`, `getByLabelText`), not implementation.
- `npm run typecheck && npm run lint && npm test` must pass.
