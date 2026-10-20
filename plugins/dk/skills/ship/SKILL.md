---
name: ship
description: Deploy to a NON-PROD environment - docker compose over SSH (java-spring, k6 smoke, backup check) or Cloudflare Workers + D1 (stack profile, health check, auto-rollback) - then sync docs.
argument-hint: "[env name in deploy/envs/, default staging]"
arguments: [env]
disable-model-invocation: true
allowed-tools: Read, Edit, Bash, Agent
---

## Environment
!`ls deploy/envs/ 2>/dev/null || echo "no deploy/envs - create deploy/envs/staging.env from deploy/envs/example.env"`

Target env: `$env` (default `staging`). Production is blocked by a hook and must be deployed by a human.

## Stack
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk_stack.py" deploy 2>/dev/null | grep -E '^(kind|nonprod_envs)=' || echo "kind=compose-ssh (java-spring)"`

## Cloudflare (`kind=cloudflare` above)
Use these steps instead of the Docker Compose steps below.
1. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/deploy-cf.sh" ${env:-staging}` - refuses an uncommitted tree and any env not in `nonprod_envs`; builds (`deploy.build`), applies D1 migrations (expand-only) with `--remote --env`, runs `wrangler deploy --env`, checks `<url><health>`, records `.dk/releases/<env>.log`. Health failure ⇒ it rolls the code back to the previous good version by itself; report it and stop.
2. Smoke: `curl -fsS "$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/deploy-cf.sh" ${env:-staging} --url)/api/health"` plus one read endpoint the BRD names as critical. (No k6 for Cloudflare in this version.)
3. Rollback on request: `deploy-cf.sh ${env:-staging} --rollback [version-id]` - code only; D1 data is never rolled back by an agent (D1 Time Travel is the human's decision, docs/runbook.md).
4. Scheduled jobs (pipeline): if `.github/workflows/` has a `schedule:` workflow that is not enabled yet, remind the human - `ship` does not run it.
5. Delegate to `doc-sync` ("Sync docs for the changes deployed since the last tag"), then `git tag ${env:-staging}-$(date +%Y%m%d-%H%M)` and commit doc changes together with `.dk/releases/`.
6. Reply in Vietnamese, max 5 lines: URL, version id, git sha, health result, rollback if any.

## Docker Compose (java-spring)
1. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/deploy.sh" ${env:-staging}` - refuses an uncommitted tree, builds images locally, ships them over SSH (`docker save | ssh docker load`, no registry needed), runs `docker compose up -d`, waits for `/api/actuator/health`, records the tag in `releases.log` on the host. Health failure → run `deploy.sh ${env:-staging} --rollback` at once (previous tag; images stay on the host and migrations are expand-only), then report.
2. `k6 run -e BASE_URL=$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/deploy.sh" ${env:-staging} --url) deploy/k6/smoke.js` (you never read `deploy/envs/*.env` yourself - the guard hook blocks it) - thresholds in the script are the NFRs from the BRD. Report p95 and error rate. Failure = `deploy.sh ${env:-staging} --rollback`, then stop and report.
3. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/deploy.sh" ${env:-staging} --verify-backup` - runs a backup and restores it into a scratch database, compares row counts.
4. Delegate to `doc-sync`: "Sync docs for the changes deployed since the last tag". Then `git tag ${env:-staging}-$(date +%Y%m%d-%H%M)` and commit doc changes.
5. Reply in Vietnamese, max 6 lines: URL, version/tag, p95, error rate, backup check result.
