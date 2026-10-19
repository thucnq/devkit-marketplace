# Review checklist — Python / TypeScript / Cloudflare (dk stack profile)

Use instead of the Spring checks (2–6) in the reviewer prompt. Report only findings with file:line and a concrete fix.

1. **Contract drift** — every `/api/*` route matches `docs/api/openapi.yaml` (path, method, status codes, fields, required-ness, problem+json errors).
2. **Injection** — D1 SQL built with string concatenation/template literals; dynamic `ORDER BY`/column names without an allow-list; user input in shell commands (`subprocess` with `shell=True`), file paths or HTML (`dangerouslySetInnerHTML`).
3. **Input & abuse** — write endpoints without validation (size, type, enum), without rate limiting, or trusting client-sent ids/scores/"first" flags the server could verify; missing `AC-<FEAT>-ABUSE` test.
4. **Secrets & environments** — secrets read anywhere but `env`/environment variables; secrets logged or written to artifacts; `wrangler` commands or workflows that could reach production without the human gate; CI jobs with more `permissions` than needed; third-party actions not pinned to a major version.
5. **Personal data** — anything beyond the stated minimum (anonymous id, nickname) stored or logged; raw IPs kept; user data sent to an LLM or third party; missing retention.
6. **Determinism & idempotency (pipeline)** — clock/random/network inside logic; unstable ordering in published artifacts; partial publish on failure; no backoff/timeout on network calls; LLM output used without schema validation.
7. **Content safety** — generated/crawled content reaching users without the moderation step the ACs require; blocklists bypassable by case/diacritics/spacing (compare on folded text).
8. **D1 schema** — destructive migration, missing index for a query the code runs, unbounded `SELECT` without `LIMIT`, non-atomic multi-statement writes (use `batch`).
9. **Frontend** — unhandled error/empty states, layout broken at 375 px, sensitive data in `localStorage`, missing `try/catch` around storage access.
