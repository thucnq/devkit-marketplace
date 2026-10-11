#!/usr/bin/env bash
# Injects a ~5-line project status at session start (stdout → context). Silent outside dk projects.
[ -f .dk/state.md ] || exit 0
echo "## dk project state"
grep -vE '^#|^$' .dk/state.md | head -12
b="$(git branch --show-current 2>/dev/null)"; [ -n "$b" ] && echo "branch: $b ($(git status --porcelain 2>/dev/null | wc -l | tr -d ' ') uncommitted files)"
[ -f .dk/check-report.md ] && echo "last check: $(head -1 .dk/check-report.md)"
echo "Workflow: /dk:spec (đề xuất phạm vi) → chốt docs/scope.md → /dk:spec → /dk:approve spec → /dk:estimate → /dk:design → /dk:approve contract → /dk:build <feature> → /dk:review → (human merges) → /dk:ship"
exit 0
