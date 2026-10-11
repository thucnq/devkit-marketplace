#!/usr/bin/env sh
# Daily backup (cron on the server: 0 2 * * * cd /opt/<app> && ./backup.sh). Keeps 7 local copies.
# Off-site copy when RCLONE_REMOTE is set in .env (e.g. a free Google Drive / B2 remote).
set -eu
cd "$(dirname "$0")"
. ./.env
mkdir -p backups
f="backups/db-$(date +%Y%m%d-%H%M).dump"
docker compose exec -T db pg_dump -U "$DB_OWNER_USER" -d "${POSTGRES_DB:-app}" -Fc > "$f"
tar -czf "$f.files.tgz" -C "$(docker volume inspect -f '{{ .Mountpoint }}' "${APP:-goldenpath}_files" 2>/dev/null || echo /nonexistent)" . 2>/dev/null || true
ls -1t backups/db-*.dump 2>/dev/null | tail -n +8 | while read -r old; do rm -f "$old" "$old.files.tgz"; done
if [ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null 2>&1; then rclone copy backups "$RCLONE_REMOTE" --max-age 2d; fi
echo "backup ok: $f ($(du -h "$f" | cut -f1))"
