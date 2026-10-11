---
name: approve
description: Record the human's approval of a gate (spec or contract). The approval is executed before Claude sees this message, so only a human typing the command can approve.
argument-hint: spec | contract
arguments: [gate]
disable-model-invocation: true
allowed-tools: Bash
---

!`"${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" approve "$gate"`

Repeat the line above to the user verbatim and stop. If it says approved, mention the next command (`spec` → `/dk:estimate` then `/dk:design`; `contract` → `/dk:build <feature>`).
