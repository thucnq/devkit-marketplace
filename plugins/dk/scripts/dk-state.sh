#!/usr/bin/env bash
# Tiny key: value store in .dk/state.md — the only writer of that file.
# Usage: dk-state.sh get <key> | set <key> <value> | approve <gate> | require <gate> | show
set -euo pipefail
F=".dk/state.md"
EV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dk_event.py"
log() { python3 "$EV" "$@" >/dev/null 2>&1 || true; }
mkdir -p .dk
[ -f "$F" ] || printf '# dk state (managed by dk-state.sh — do not edit)\nphase: new\n' > "$F"

get() { grep -E "^$1:" "$F" | head -1 | sed -E "s/^$1:[[:space:]]*//" || true; }
set_kv() {
  local k="$1"; shift; local v="$*"
  if grep -qE "^$k:" "$F"; then
    local tmp; tmp="$(mktemp)"
    awk -v k="$k" -v v="$v" 'BEGIN{FS=":"} $1==k {print k ": " v; next} {print}' "$F" > "$tmp" && mv "$tmp" "$F"
  else
    echo "$k: $v" >> "$F"
  fi
}

case "${1:-show}" in
  show) cat "$F" ;;
  get) get "$2" ;;
  set)
    k="$2"; shift 2; set_kv "$k" "$@"; echo "$k: $*"; log state key="$k" value="$*"
    # a re-drafted upstream artefact invalidates downstream approvals
    if [ "$k" = spec ] && [[ "$*" != approved* ]]; then
      set_kv phase spec
      [[ "$(get contract)" == approved* ]] && set_kv contract "stale (spec changed $(date +%F))" && echo "contract: stale — cần /dk:design và duyệt lại"
    fi
    if [ "$k" = contract ] && [[ "$*" != approved* ]]; then set_kv phase design; fi
    ;;
  approve)
    gate="${2:?gate required: spec | contract}"
    case "$gate" in spec|contract) ;; *) echo "unknown gate '$gate' (spec | contract)"; exit 1 ;; esac
    who="$(git config user.name 2>/dev/null || whoami)"
    rev="$(git rev-parse --short HEAD 2>/dev/null || echo none)"
    if [ -n "$(git status --porcelain docs 2>/dev/null)" ]; then
      echo "⛔ docs/ có thay đổi chưa commit — commit trước khi duyệt để biết chính xác đã duyệt phiên bản nào."; exit 0
    fi
    set_kv "$gate" "approved $(date +%F) by $who at $rev"
    [ "$gate" = spec ] && set_kv phase design
    [ "$gate" = contract ] && set_kv phase build
    log gate gate="$gate" rev="$rev"
    echo "✅ Đã duyệt cổng '$gate' tại commit $rev bởi $who."
    ;;
  require)
    gate="$2"; v="$(get "$gate")"
    if [[ "$v" == approved* ]]; then
      echo "Gate '$gate': $v"
      rev="${v##* at }"
      if [ "$rev" != none ] && git rev-parse -q --verify "$rev" >/dev/null 2>&1; then
        changed="$(git diff --name-only "$rev" HEAD -- docs/brd.md docs/acceptance docs/api 2>/dev/null | head -5)"
        if [ -n "$changed" ]; then echo "⚠️ Spec/contract đã đổi sau khi duyệt: $changed — báo người dùng cân nhắc duyệt lại."; fi
      fi
    else
      log gate_blocked gate="$gate"
      echo "⛔ GATE BLOCKED: '$gate' chưa được duyệt (hiện tại: ${v:-chưa có}). DỪNG LẠI. Báo người dùng xem lại tài liệu rồi chạy /dk:approve $gate."
    fi
    ;;
  *) echo "usage: dk-state.sh get|set|approve|require|show"; exit 1 ;;
esac
