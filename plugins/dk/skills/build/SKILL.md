---
name: build
description: Implement one feature test-first — acceptance tests are written by the isolated test-author agent, then the implementation is written until they pass.
argument-hint: <feature-slug>
arguments: [feature]
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

## Gate
!`bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" require contract`

## Feature
!`test -f docs/acceptance/$feature.md && grep "^### AC-" docs/acceptance/$feature.md || echo "MISSING docs/acceptance/$feature.md"`

## Steps
1. `git switch -c feat/$feature` (or switch to it if it exists). Set state: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" set feature $feature`.
2. **Tests first.** Delegate to the `test-author` subagent: "Write acceptance tests for docs/acceptance/$feature.md". Do not write or edit those tests yourself afterwards, except to fix compilation against real class names — and never change what they assert. If an assertion is wrong, it means the AC is wrong: stop and ask the human.
3. **Implement.** Follow `${CLAUDE_PLUGIN_ROOT}/skills/spring-conventions/SKILL.md` (backend) and `${CLAUDE_PLUGIN_ROOT}/skills/react-conventions/SKILL.md` (frontend) — read only the sections you need. Package-by-feature under `<base>.feature.$feature`. Reuse golden path building blocks (`TenantContext`, `AuditService`, `@Pii`, `PiiEncryptedConverter`, `ProblemDetails` handler) — never reimplement them.
4. Loop: `./mvnw -q -pl backend test -Dtest='*$feature*'` → fix → repeat. Read only the failing test output (`-q` + `grep -A20 FAIL` style), not full logs. Max 6 iterations; if still red, stop and report what is blocking.
5. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-check.sh" quick`. Fix everything it reports.
6. Commit in small logical commits (`feat($feature): ...`). Do not push.
7. Reply in Vietnamese, max 6 lines: ACs passing x/y, files changed, anything deferred. Suggest `/dk:review` next.

Token discipline: don't re-read files you already have in context; use Grep to locate before Read; never cat build logs whole.
