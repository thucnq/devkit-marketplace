---
name: review
description: Pre-merge pipeline - run all deterministic checks, fix failures, get an independent review from the reviewer agent, then open a PR with the AC traceability table.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, Agent
---

## Branch
!`git branch --show-current; git log --oneline origin/main..HEAD 2>/dev/null | head -20 || git log --oneline -10`

## Stack
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk_stack.py" info 2>/dev/null || echo "stack: java-spring (không có .dk/stack.toml)"`

## Steps
1. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-check.sh" full` (writes `.dk/check-report.md`). With a stack profile it runs each component's format/lint/typecheck/tests with coverage/build (see the report rows) plus the shared checks below; without one (java-spring) it runs: `mvn verify` (all tests, JaCoCo, ArchUnit, Spotless, SpotBugs, PMD), AC traceability, OpenAPI lint, gitleaks, Semgrep, osv-scanner (vulnerable dependencies), frontend typecheck/lint/test/build. Tools that are not installed are reported as SKIPPED, not passed - mention them.
2. If anything FAILED: fix it and re-run, max 3 rounds. Do not weaken a check (no `@Disabled`, no suppressions, no lowering thresholds) without asking the human.
3. Delegate to the `reviewer` subagent: "Review branch <branch> against origin/main" - add "Stack: <the Stack line above>" so it picks the right checklist. If the feature's line in `docs/plan/tien-do.md` (or its item in `docs/estimate/items.json`) says `rủi ro: HIGH`, add: "Risk HIGH - apply the full security-baseline checklist (tenancy, authorization, PII, audit) and check every AC-INV that touches this feature." 
4. If VERDICT is CHANGES_REQUIRED: fix every Blocker, re-run step 1 quick (`dk-check.sh quick`), then ask the reviewer once more. Second CHANGES_REQUIRED → stop and show the blockers to the human.
5. On APPROVE: `git push -u origin HEAD` and create the PR with `gh pr create --title "<type(feature): summary>" --body-file .dk/pr-body.md` where `.dk/pr-body.md` = `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ac-trace.py" --markdown` output + `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk-evidence.py" report <feature>` (RED → GREEN per AC) + the reviewer's "Should fix" list. Set state `review: approved` for this branch via `dk-state.sh set review-$(git branch --show-current | tr / -) approved`.
6. Reply in Vietnamese, max 5 lines with the PR URL. Merging is the human's job (the guard hook blocks `gh pr merge` for the agent; CI must be green on the PR).

Waiting on long commands (tests, `dk-check.sh`): run the command itself with `run_in_background: true` (one background command per component when running them in parallel) and wait for its completion notification. Never poll with `until/while pgrep -f ...` - it matches its own command line and spins forever (the guard blocks it); never start jobs with `&` inside a pipe and `wait` outside it. A background task running longer than 10 minutes must be re-evaluated, not waited on silently: note the start time when you launch it; at your next turn (any user message or notification) past 10 minutes, check that the process is still alive (`ps -o etime,args -p <pid>`), that its output is still growing, and how long the same command took last time (`.dk/log`, earlier output). Then tell the user in one line what you found: still progressing normally (and the expected end), or stuck - stop it and re-run it narrower (one component, one test file).
