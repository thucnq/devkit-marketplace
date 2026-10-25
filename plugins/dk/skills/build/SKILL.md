---
name: build
description: Implement one feature test-first - acceptance tests are written by the isolated test-author agent, then the implementation is written until they pass.
argument-hint: <feature-slug>
arguments: [feature]
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

## Gate
!`bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" require contract`

## Feature
!`test -f docs/acceptance/$feature.md && grep "^### AC-" docs/acceptance/$feature.md || echo "MISSING docs/acceptance/$feature.md"`

## Stack
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk_stack.py" test-cmd $feature 2>/dev/null || echo "java-spring (không có .dk/stack.toml): dùng lệnh Maven ở các bước dưới"`

With a stack profile (lines above: `<component>  <dir>  <command>`), **replace every Maven command below with the commands above**, run in their directory (`cd <dir> && <command>`), for the components that hold this feature's tests; they already filter by the feature's AC ids and write JUnit XML to `.dk/junit/` for `dk-evidence.py`. Conventions: `${CLAUDE_PLUGIN_ROOT}/skills/python-conventions/SKILL.md` (pipeline) and `${CLAUDE_PLUGIN_ROOT}/skills/cf-worker-conventions/SKILL.md` (worker, web) instead of the Spring/React ones. "Compile" for RED means `npm run typecheck` / `python3 -m pytest --collect-only`.

## Steps
1. `git switch -c feat/$feature` (or switch to it if it exists). Set state: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" set feature $feature`.
2. **Tests first.** Delegate to the `test-author` subagent: "Write acceptance tests for docs/acceptance/$feature.md". Do not write or edit those tests yourself afterwards, except to fix compilation against real class names - and never change what they assert. If an assertion is wrong, it means the AC is wrong: stop and ask the human.
2b. **RED evidence.** Run the feature's tests once before writing any production code (`./mvnw -q -pl backend test -Dtest='<Feature>*' -Dsurefire.failIfNoSpecifiedTests=false || true`, where `<Feature>` is the PascalCase class prefix test-author used, e.g. `Cty` for `cty` - Surefire patterns are case-sensitive, `*cty*` matches nothing), then `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk-evidence.py" red $feature` (add `--compile` when the tests cannot compile yet because production classes do not exist). Mandatory ACs with no test → back to test-author. ACs that PASS already ("⚠ xanh trước khi code") mean the test asserts nothing new: tell test-author to tighten them (or confirm the behaviour already exists in the golden path) before implementing.
3. **Implement.** Follow `${CLAUDE_PLUGIN_ROOT}/skills/spring-conventions/SKILL.md` (backend) and `${CLAUDE_PLUGIN_ROOT}/skills/react-conventions/SKILL.md` (frontend) - read only the sections you need. Package-by-feature under `<base>.feature.$feature`. Reuse golden path building blocks (`TenantContext`, `AuditService`, `@Pii`, `PiiEncryptedConverter`, `ProblemDetails` handler) - never reimplement them.
4. Loop: `./mvnw -q -pl backend test -Dtest='<Feature>*'` → fix → repeat. Read only the failing test output (`-q` + `grep -A20 FAIL` style), not full logs. Max 6 iterations; if still red, stop and report what is blocking.
5. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk-evidence.py" green $feature` (exit 1 = a mandatory AC is not green: keep going). Then run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-check.sh" quick`. Fix everything it reports.
6. Commit in small logical commits (`test($feature): …` for the RED tests, then `feat($feature): …`), including `.dk/evidence/$feature.json`. Do not push.
7. Reply in Vietnamese, max 6 lines: ACs passing x/y, files changed, anything deferred. Suggest `/dk:review` next.

Waiting on long commands (tests, `dk-check.sh`): run the command itself with `run_in_background: true` (one background command per component when running them in parallel) and wait for its completion notification. Never poll with `until/while pgrep -f ...` - it matches its own command line and spins forever (the guard blocks it); never start jobs with `&` inside a pipe and `wait` outside it.

Token discipline: don't re-read files you already have in context; use Grep to locate before Read; never cat build logs whole.
