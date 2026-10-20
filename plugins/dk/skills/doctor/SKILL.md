---
name: doctor
description: Check that this machine can run the dk workflow (WSL2 Ubuntu, repo on the Linux filesystem, LF line endings, Java 21, Docker, Node 22, gh, Claude Code) and explain how to fix what is missing.
argument-hint: "[--fix | --install-launcher]"
disable-model-invocation: true
allowed-tools: Bash, Read
---

## Result
!`bash "${CLAUDE_PLUGIN_ROOT}/scripts/wsl-doctor.sh" $ARGUMENTS 2>&1 | tail -60`

## Task
Reply in Vietnamese, max 12 lines:
1. One line verdict: ready / not ready (count FAIL, WARN).
2. For each FAIL, the exact command to fix it (copy it from the output). Group WARNs into one line.
3. If the output says the session runs on Windows (MINGW/MSYS/CYGWIN) or the repo is under `/mnt/<drive>/`: point to `docs/dev/wsl-intellij.md` (golden path) or `${CLAUDE_PLUGIN_ROOT}/templates/golden-path/docs/dev/wsl-intellij.md`, section "Bước 1–2", and stop.
4. Never run `sudo`, `apt`, `--fix` or `--install-launcher` yourself unless the user passed that flag in this command - suggest them.
