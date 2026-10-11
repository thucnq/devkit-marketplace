---
name: ship
description: Deploy to a NON-PROD environment (docker compose over SSH), run the k6 smoke test with NFR thresholds, verify backup/restore, then sync docs.
argument-hint: "[env name in deploy/envs/, default staging]"
arguments: [env]
disable-model-invocation: true
allowed-tools: Read, Edit, Bash, Agent
---

## Environment
!`ls deploy/envs/ 2>/dev/null || echo "no deploy/envs — create deploy/envs/staging.env from deploy/envs/example.env"`

Target env: `$env` (default `staging`). Production is blocked by a hook and must be deployed by a human.

## Steps
1. `"${CLAUDE_PLUGIN_ROOT}/scripts/deploy.sh" ${env:-staging}` — builds images locally, ships them over SSH (`docker save | ssh docker load`, no registry needed), runs `docker compose up -d`, waits for `/actuator/health`.
2. `k6 run -e BASE_URL=$("${CLAUDE_PLUGIN_ROOT}/scripts/deploy.sh" ${env:-staging} --url) deploy/k6/smoke.js` (you never read `deploy/envs/*.env` yourself — the guard hook blocks it) — thresholds in the script are the NFRs from the BRD. Report p95 and error rate. Failure = do not continue.
3. `"${CLAUDE_PLUGIN_ROOT}/scripts/deploy.sh" ${env:-staging} --verify-backup` — runs a backup and restores it into a scratch database, compares row counts.
4. Delegate to `doc-sync`: "Sync docs for the changes deployed since the last tag". Then `git tag ${env:-staging}-$(date +%Y%m%d-%H%M)` and commit doc changes.
5. Reply in Vietnamese, max 6 lines: URL, version/tag, p95, error rate, backup check result.
