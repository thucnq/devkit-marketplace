---
name: review
description: Pre-merge pipeline — run all deterministic checks, fix failures, get an independent review from the reviewer agent, then open a PR with the AC traceability table.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, Agent
---

## Branch
!`git branch --show-current; git log --oneline origin/main..HEAD 2>/dev/null | head -20 || git log --oneline -10`

## Steps
1. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-check.sh" full` (writes `.dk/check-report.md`). It runs: `mvn verify` (all tests, JaCoCo, ArchUnit, Spotless, SpotBugs, PMD), AC traceability, OpenAPI lint, gitleaks, Semgrep, osv-scanner (vulnerable dependencies), frontend typecheck/lint/test/build. Tools that are not installed are reported as SKIPPED, not passed — mention them.
2. If anything FAILED: fix it and re-run, max 3 rounds. Do not weaken a check (no `@Disabled`, no suppressions, no lowering thresholds) without asking the human.
3. Delegate to the `reviewer` subagent: "Review branch <branch> against origin/main". 
4. If VERDICT is CHANGES_REQUIRED: fix every Blocker, re-run step 1 quick (`dk-check.sh quick`), then ask the reviewer once more. Second CHANGES_REQUIRED → stop and show the blockers to the human.
5. On APPROVE: `git push -u origin HEAD` and create the PR with `gh pr create --title "<type(feature): summary>" --body-file .dk/pr-body.md` where `.dk/pr-body.md` = `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ac-trace.py" --markdown` output + the reviewer's "Should fix" list. Set state `review: approved` for this branch via `dk-state.sh set review-$(git branch --show-current | tr / -) approved`.
6. Reply in Vietnamese, max 5 lines with the PR URL. Merging is the human's job (the guard hook blocks `gh pr merge` for the agent; CI must be green on the PR).
