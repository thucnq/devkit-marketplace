#!/usr/bin/env bash
# Chạy Claude Code Remote Control trong tmux để điều khiển từ điện thoại / claude.ai/code.
# Chạy trong thư mục gốc của dự án (trong WSL hoặc Linux):
#   dk-remote.sh [start]   khởi động, hoặc báo đang chạy
#   dk-remote.sh stop      dừng (không tự khởi động lại)
#   dk-remote.sh resume    khởi động lại, lấy lại hội thoại gần nhất (--continue)
#   dk-remote.sh attach    gắn vào tmux (thoát mà không dừng: Ctrl+B rồi D)
#   dk-remote.sh status    còn chạy không, đã tự khởi động lại mấy lần
# `claude remote-control` tự thoát khi mất mạng quá ~10 phút: vòng lặp trong tmux chạy lại sau 30 giây
# với --continue (lấy lại hội thoại) cho tới khi gọi `stop`. Bài học từ runbook hopnhat.
# Cờ bổ sung cho `claude remote-control`: biến DK_REMOTE_FLAGS (vd "--spawn session").
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
command -v tmux >/dev/null || { echo "Thiếu tmux: sudo apt install -y tmux"; exit 1; }
command -v claude >/dev/null || { echo "Thiếu Claude Code: curl -fsSL https://claude.ai/install.sh | bash"; exit 1; }
git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "Chạy trong thư mục git của dự án."; exit 1; }
cd "$(git rev-parse --show-toplevel)"
case "$PWD" in /mnt/[a-z]/*) echo "⛔ Repo đang nằm trên ổ Windows ($PWD). Chuyển vào ~/ trong WSL (xem docs/dev/wsl-intellij.md)."; exit 1 ;; esac

slug="$(sed -nE 's/^project:[[:space:]]*//p' .dk/state.md 2>/dev/null | head -1)"
[ -n "$slug" ] || slug="$(basename "$PWD")"
NAME="dk-$slug"
RUN="${XDG_STATE_HOME:-$HOME/.local/state}/dk-remote"; mkdir -p "$RUN"
STOP="$RUN/$NAME.stop"; RESTARTS="$RUN/$NAME.restarts"

case "${1:-start}" in
  _loop)  # chạy bên trong tmux
    shift; extra="${1:-}"; rm -f "$STOP"; echo 0 > "$RESTARTS"
    while :; do
      # shellcheck disable=SC2086
      claude remote-control --name "$slug" ${DK_REMOTE_FLAGS:-} $extra || true
      [ -f "$STOP" ] && break
      echo "$(( $(cat "$RESTARTS" 2>/dev/null || echo 0) + 1 ))" > "$RESTARTS"
      echo "$(date '+%F %T') Claude Code thoát (mất mạng?) — chạy lại sau 30 giây. Dừng hẳn: dk-remote stop"
      sleep 30; extra="--continue"
    done
    echo "Đã dừng — Enter để đóng"; read -r _ ;;
  stop)
    touch "$STOP"
    tmux send-keys -t "$NAME" C-c 2>/dev/null || true; sleep 2
    tmux kill-session -t "$NAME" 2>/dev/null || true; echo "đã dừng $NAME"; exit 0 ;;
  attach) exec tmux attach -t "$NAME" ;;
  status)
    if tmux has-session -t "$NAME" 2>/dev/null; then
      echo "$NAME đang chạy · tự khởi động lại $(cat "$RESTARTS" 2>/dev/null || echo 0) lần"
    else echo "$NAME không chạy"; exit 1; fi
    exit 0 ;;
  resume|start)
    extra=""; [ "${1:-start}" = resume ] && extra="--continue"
    if tmux has-session -t "$NAME" 2>/dev/null; then
      echo "Đang chạy. Gắn vào: tmux attach -t $NAME"; exit 0
    fi
    tmux new-session -d -s "$NAME" -c "$PWD" "bash '$SELF' _loop '$extra'"
    sleep 2
    echo "Đã chạy trong tmux phiên '$NAME' (tự khởi động lại khi claude thoát)."
    echo "• Lần đầu: tmux attach -t $NAME → trả lời y cho 'Enable Remote Control?' / 'Trust…?' → Ctrl+B rồi D."
    echo "• Điện thoại: app Claude → Code → phiên '$slug' (chấm xanh = online). Web: claude.ai/code" ;;
  *) echo "dùng: dk-remote.sh [start|stop|resume|attach|status]"; exit 1 ;;
esac
