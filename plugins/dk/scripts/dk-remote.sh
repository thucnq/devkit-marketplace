#!/usr/bin/env bash
# Chạy Claude Code Remote Control trong tmux để điều khiển từ điện thoại / claude.ai/code.
# Chạy trong thư mục gốc của dự án (trong WSL hoặc Linux):
#   dk-remote.sh [start]   khởi động, hoặc báo đang chạy
#   dk-remote.sh stop      dừng
#   dk-remote.sh resume    khởi động lại, lấy lại hội thoại gần nhất (--continue)
#   dk-remote.sh attach    gắn vào tmux (thoát mà không dừng: Ctrl+B rồi D)
# Cờ bổ sung cho `claude remote-control`: biến DK_REMOTE_FLAGS (vd "--spawn session").
set -euo pipefail
command -v tmux >/dev/null || { echo "Thiếu tmux: sudo apt install -y tmux"; exit 1; }
command -v claude >/dev/null || { echo "Thiếu Claude Code: curl -fsSL https://claude.ai/install.sh | bash"; exit 1; }
git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "Chạy trong thư mục git của dự án."; exit 1; }
cd "$(git rev-parse --show-toplevel)"
case "$PWD" in /mnt/[a-z]/*) echo "⛔ Repo đang nằm trên ổ Windows ($PWD). Chuyển vào ~/ trong WSL (xem docs/dev/wsl-intellij.md)."; exit 1 ;; esac

slug="$(sed -nE 's/^project:[[:space:]]*//p' .dk/state.md 2>/dev/null | head -1)"
[ -n "$slug" ] || slug="$(basename "$PWD")"
NAME="dk-$slug"

case "${1:-start}" in
  stop)
    tmux send-keys -t "$NAME" C-c 2>/dev/null || true; sleep 2
    tmux kill-session -t "$NAME" 2>/dev/null || true; echo "đã dừng $NAME"; exit 0 ;;
  attach) exec tmux attach -t "$NAME" ;;
  resume) extra="--continue" ;;
  start) extra="" ;;
  *) echo "dùng: dk-remote.sh [start|stop|resume|attach]"; exit 1 ;;
esac

if tmux has-session -t "$NAME" 2>/dev/null; then
  echo "Đang chạy. Gắn vào: tmux attach -t $NAME"; exit 0
fi
# shellcheck disable=SC2086
tmux new-session -d -s "$NAME" -c "$PWD" \
  "claude remote-control --name '$slug' ${DK_REMOTE_FLAGS:-} $extra; echo; echo 'Claude Code đã dừng — Enter để đóng'; read"
sleep 2
echo "Đã chạy trong tmux phiên '$NAME'."
echo "• Lần đầu: tmux attach -t $NAME → trả lời y cho 'Enable Remote Control?' / 'Trust…?' → Ctrl+B rồi D."
echo "• Điện thoại: app Claude → Code → phiên '$slug' (chấm xanh = online). Web: claude.ai/code"
