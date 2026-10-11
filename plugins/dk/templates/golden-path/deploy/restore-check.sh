#!/usr/bin/env sh
# Proves the latest backup restores: loads it into a scratch DB and compares row counts.
set -eu
cd "$(dirname "$0")"
. ./.env
latest="$(ls -1t backups/db-*.dump | head -1)"
db="${POSTGRES_DB:-app}"
psql() { docker compose exec -T db psql -U "$DB_OWNER_USER" -v ON_ERROR_STOP=1 -qtA "$@"; }
psql -d postgres -c "drop database if exists restore_check" -c "create database restore_check"
docker compose exec -T db pg_restore -U "$DB_OWNER_USER" -d restore_check --no-owner < "$latest"
q="select relname || '=' || n_live_tup from pg_stat_user_tables where relname not like 'audit_event_%' order by 1"
psql -d "$db" -c "analyze" >/dev/null; psql -d restore_check -c "analyze" >/dev/null
live="$(psql -d "$db" -c "$q")"; restored="$(psql -d restore_check -c "$q")"
psql -d postgres -c "drop database restore_check"
if [ "$live" = "$restored" ]; then echo "restore check ok ($latest)"; else echo "restore check MISMATCH"; echo "live: $live"; echo "restored: $restored"; exit 1; fi
