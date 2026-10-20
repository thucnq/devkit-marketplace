#!/usr/bin/env bash
# Non-prod deploy over SSH with docker compose - no registry needed.
# Usage: deploy.sh <env> [--url | --verify-backup | --rollback [tag] | --releases]
#   --rollback: start the previous release (or <tag>) again; images stay on the host and migrations are
#               expand-only, so the old code runs on the new schema (idea from hopnhat rollback.sh).
# Reads deploy/envs/<env>.env : DEPLOY_HOST (user@host | local), DEPLOY_DIR, PUBLIC_URL, + app variables.
set -euo pipefail
ENV_NAME="${1:?usage: deploy.sh <env> [--url|--verify-backup|--rollback [tag]|--releases]}"
ACTION="${2:-deploy}"
case "$ENV_NAME" in prod*) echo "⛔ production deploys are human-only (run the same steps manually)"; exit 2 ;; esac
ENV_FILE="deploy/envs/$ENV_NAME.env"
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE (copy deploy/envs/example.env)"; exit 1; }
val() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2-; }
HOST="$(val DEPLOY_HOST)"; DIR="$(val DEPLOY_DIR)"; URL="$(val PUBLIC_URL)"
DIR="${DIR:-/opt/$(basename "$PWD")}"
[ "$ACTION" = "--url" ] && { echo "$URL"; exit 0; }

remote() { if [ "$HOST" = local ]; then (cd "$DIR" && bash -c "$1"); else ssh -o BatchMode=yes "$HOST" "cd '$DIR' && $1"; fi; }
copy() { if [ "$HOST" = local ]; then mkdir -p "$DIR" && cp "$@" "$DIR/"; else ssh "$HOST" "mkdir -p '$DIR'" && scp -q "$@" "$HOST:$DIR/"; fi; }

APP="$(basename "$PWD")"
health() {
  for _ in $(seq 1 30); do
    curl -fsS "$URL/api/actuator/health" >/dev/null 2>&1 && return 0
    sleep 4
  done
  return 1
}

if [ "$ACTION" = "--verify-backup" ]; then
  remote "sh ./backup.sh && sh ./restore-check.sh"
  exit $?
fi
if [ "$ACTION" = "--releases" ]; then
  remote "tail -n 10 releases.log 2>/dev/null || echo 'chưa có releases.log'"; exit 0
fi
if [ "$ACTION" = "--rollback" ]; then
  CUR="$(remote "tail -n 1 releases.log 2>/dev/null | cut -d' ' -f2")"
  PREV="${3:-$(remote "cut -d' ' -f2 releases.log 2>/dev/null | grep -vx '$CUR' | tail -n 1")}"
  [ -n "$PREV" ] || { echo "❌ không có bản trước trong releases.log"; exit 1; }
  echo "▶ rollback $APP: $CUR → $PREV"
  remote "APP=$APP TAG=$PREV docker compose up -d --remove-orphans && echo \"\$(date -u +%FT%TZ) $PREV rollback\" >> releases.log"
  if health; then echo "✅ $URL chạy lại bản $PREV"; exit 0; fi
  echo "❌ rollback xong nhưng health vẫn lỗi:"; remote "docker compose logs --tail=40 api"; exit 1
fi

if [ -n "$(git status --porcelain)" ] && [ "${DK_ALLOW_DIRTY:-}" != 1 ]; then
  echo "⛔ cây làm việc có thay đổi chưa commit - commit trước để bản deploy truy được về một commit (DK_ALLOW_DIRTY=1 để bỏ qua)"
  exit 1
fi
TAG="$(git rev-parse --short HEAD)$( [ -n "$(git status --porcelain)" ] && echo -dirty)"
echo "▶ building $APP:$TAG"
MVN=mvn; [ -x ./mvnw ] && MVN=./mvnw
$MVN -q -B -DskipTests package
npm --prefix frontend ci --silent && npm --prefix frontend run -s build
docker build -q -t "$APP-api:$TAG" -f deploy/Dockerfile.api .
docker build -q -t "$APP-web:$TAG" -f deploy/Dockerfile.web .

echo "▶ shipping to $HOST:$DIR"
copy deploy/compose.yml deploy/Caddyfile deploy/backup.sh deploy/restore-check.sh
copy "$ENV_FILE"; remote "mv -f '$ENV_NAME.env' .env && chmod 600 .env && chmod +x *.sh"
if [ "$HOST" != local ]; then
  docker save "$APP-api:$TAG" "$APP-web:$TAG" | gzip | ssh "$HOST" 'gunzip | docker load' >/dev/null
fi
remote "APP=$APP TAG=$TAG docker compose up -d --remove-orphans"

echo "▶ waiting for health"
if health; then
  remote "echo \"\$(date -u +%FT%TZ) $TAG deploy\" >> releases.log"
  echo "✅ $URL is healthy ($TAG)"; exit 0
fi
echo "❌ health check failed - last logs:"; remote "docker compose logs --tail=40 api"
echo "   quay lại bản trước: deploy.sh $ENV_NAME --rollback"; exit 1
