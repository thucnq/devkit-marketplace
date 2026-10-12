#!/usr/bin/env bash
# Injects a ~6-line project status at session start (stdout → context). Silent outside dk projects.
[ -f .dk/state.md ] || exit 0
echo "## dk project state"
grep -vE '^#|^$' .dk/state.md | head -12
b="$(git branch --show-current 2>/dev/null)"; [ -n "$b" ] && echo "branch: $b ($(git status --porcelain 2>/dev/null | wc -l | tr -d ' ') uncommitted files)"
[ -f .dk/check-report.md ] && echo "last check: $(head -1 .dk/check-report.md)"
[ -f docs/plan/tien-do.md ] && python3 "$(dirname "$0")/gen-plan.py" --summary 2>/dev/null | head -1
# Windows-native shells and repos on /mnt/<drive> are the main source of breakage (CRLF, file modes, slow I/O)
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) echo "⚠ Phiên đang chạy trên Windows (Git Bash) — dk được kiểm chứng trên WSL2. Đề nghị người dùng chạy /dk:doctor và chuyển sang WSL (docs/dev/wsl-intellij.md)." ;;
esac
case "$PWD" in /mnt/[a-z]/*) echo "⚠ Repo nằm trên ổ Windows ($PWD) — chậm và dễ lỗi CRLF/quyền file. Đề nghị chạy /dk:doctor và clone lại vào ~/ trong WSL." ;; esac
echo "Workflow: /dk:spec (đề xuất phạm vi) → chốt docs/scope.md → /dk:spec → /dk:approve spec → /dk:estimate (+ /dk:plan) → /dk:design → /dk:approve contract → /dk:build <feature> → /dk:review → (human merges) → /dk:ship"
exit 0
