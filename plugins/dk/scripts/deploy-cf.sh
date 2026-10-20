#!/usr/bin/env bash
# Non-prod deploy to Cloudflare Workers for projects whose .dk/stack.toml has deploy.kind = "cloudflare".
# Usage: deploy-cf.sh <env> [--rollback [version-id] | --releases | --url]
#   default     build (deploy.build), apply D1 migrations (expand-only), wrangler deploy --env <env>,
#               health check <url><deploy.health>; failure ⇒ wrangler rollback to the previous good version
#   --rollback  roll the Worker code back to <version-id> or to the good release before the current one.
#               D1 data is NOT rolled back (that is a human decision: D1 Time Travel, see docs/runbook.md)
#   --releases  print .dk/releases/<env>.log        --url  print the last known URL of <env>
# Production is human-only: <env> must be in deploy.nonprod_envs (and never prod*) - the guard hook blocks it too.
set -euo pipefail
ENV_NAME="${1:?usage: deploy-cf.sh <env> [--rollback [version-id] | --releases | --url]}"
ACTION="${2:-deploy}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WRANGLER_SEND_METRICS=false
case "$ENV_NAME" in prod*|"") echo "⛔ production chỉ do người triển khai (xem docs/runbook.md)"; exit 2 ;; esac

cfg="$(python3 "$HERE/dk_stack.py" deploy)" || { echo "deploy-cf: .dk/stack.toml không có thành phần deploy (kind cloudflare)"; exit 1; }
get() { echo "$cfg" | sed -n "s/^$1=//p" | head -1; }
[ "$(get kind)" = cloudflare ] || { echo "deploy-cf: deploy.kind = $(get kind), không phải cloudflare - dùng deploy.sh"; exit 1; }
ROOT="$(get root)"; HEALTH="$(get health)"; HEALTH="${HEALTH:-/api/health}"
BINDING="$(get d1_binding)"; BUILD="$(get build)"; NONPROD=" $(get nonprod_envs) "
[[ "$NONPROD" == *" $ENV_NAME "* ]] || { echo "⛔ env '$ENV_NAME' không nằm trong deploy.nonprod_envs ($NONPROD) của .dk/stack.toml"; exit 2; }

LOG=".dk/releases/$ENV_NAME.log"   # ts<TAB>git sha<TAB>version id<TAB>url<TAB>ok|failed|rollback
mkdir -p .dk/releases
wr() { (cd "$ROOT" && npx --no-install wrangler "$@"); }
last_url() { [ -f "$LOG" ] && awk -F'\t' '$4 != "" {u=$4} END {print u}' "$LOG"; }
good_versions() { [ -f "$LOG" ] && awk -F'\t' '$5 == "ok" || $5 == "rollback" {print $3}' "$LOG"; }
record() { printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$(git rev-parse --short HEAD 2>/dev/null)" "$1" "$2" "$3" >> "$LOG"; }
health() {
  local url="$1"
  for _ in $(seq 1 "${DK_HEALTH_TRIES:-30}"); do
    curl -fsS --max-time 10 "$url$HEALTH" >/dev/null 2>&1 && return 0
    sleep "${DK_HEALTH_SLEEP:-4}"
  done
  return 1
}
rollback_to() { # rollback_to <version-id> <reason>
  echo "↩ rollback $ENV_NAME → $1 ($2)"
  wr rollback "$1" --env "$ENV_NAME" -y -m "dk: $2"
  record "$1" "$(last_url)" rollback
}

case "$ACTION" in
  --url) last_url; exit 0 ;;
  --releases) [ -f "$LOG" ] && cat "$LOG" || echo "(chưa có bản phát hành nào cho $ENV_NAME)"; exit 0 ;;
  --rollback)
    target="${3:-}"
    if [ -z "$target" ]; then
      target="$(good_versions | tail -2 | head -1)"
      [ -n "$target" ] && [ "$(good_versions | wc -l)" -ge 2 ] || { echo "deploy-cf: không có bản tốt trước đó trong $LOG - truyền version-id (npx wrangler versions list --env $ENV_NAME)"; exit 1; }
    fi
    rollback_to "$target" "manual rollback"
    url="$(last_url)"; [ -z "$url" ] || health "$url" || { echo "✗ health sau rollback vẫn lỗi - báo người"; exit 1; }
    echo "✓ đã quay lại $target"; exit 0 ;;
  deploy) ;;
  *) echo "deploy-cf: thao tác $ACTION không hỗ trợ"; exit 2 ;;
esac

[ -z "$(git status --porcelain --untracked-files=no -- . ':!.dk/releases' ':!.dk/log')" ] || { echo "⛔ cây làm việc có thay đổi chưa commit - commit trước để biết chính xác bản nào được triển khai"; exit 1; }
if [ -n "$BUILD" ]; then echo "▶ build: $BUILD"; bash -c "$BUILD"; fi
if [ -n "$BINDING" ]; then echo "▶ D1 migrations ($ENV_NAME, expand-only)"; wr d1 migrations apply "$BINDING" --env "$ENV_NAME" --remote; fi
echo "▶ wrangler deploy --env $ENV_NAME"
out="$(wr deploy --env "$ENV_NAME" 2>&1)" || { echo "$out" | tail -30; record "" "" failed; exit 1; }
echo "$out" | tail -15
version="$(echo "$out" | sed -nE 's/.*Version ID:[[:space:]]*([0-9a-fA-F-]{8,}).*/\1/p' | tail -1)"
url="$(echo "$out" | grep -oE 'https://[A-Za-z0-9.-]+\.workers\.dev' | tail -1)"
url="${url:-$(last_url)}"
[ -n "$url" ] || { echo "deploy-cf: không xác định được URL (thêm route/custom domain hoặc kiểm tra output wrangler)"; record "$version" "" failed; exit 1; }
if health "$url"; then
  record "$version" "$url" ok
  echo "✓ $ENV_NAME: $url · version ${version:-?} · $(git rev-parse --short HEAD)"
else
  record "$version" "$url" failed
  prev="$(good_versions | tail -1)"
  if [ -n "$prev" ] && [ "$prev" != "$version" ]; then rollback_to "$prev" "health check failed"
  else echo "✗ health lỗi và không có bản tốt trước đó để quay lại"; fi
  exit 1
fi
