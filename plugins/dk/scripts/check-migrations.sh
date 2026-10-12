#!/usr/bin/env bash
# Flyway migrations are expand-only (idea from hopnhat ADR-007).
#   check-migrations.sh [base] [head]      default: merge-base with origin/main .. HEAD
# FAIL when, between base and head:
#   - a committed migration is modified, deleted or renamed;
#   - a new migration is not named V<yyyyMMddHHmm>__<slug>.sql (3 people on parallel branches must never collide);
#   - a new migration contains a destructive statement (DROP, RENAME, TRUNCATE, DELETE FROM, ALTER COLUMN … TYPE,
#     SET NOT NULL) — unless the file carries the line `-- dk:allow-destructive <reason>`, which the human
#     accepts at the contract gate (/dk:approve contract) or in PR review.
set -uo pipefail
DIR="backend/src/main/resources/db/migration"
base="${1:-$(git merge-base HEAD origin/main 2>/dev/null || echo HEAD~1)}"; head="${2:-HEAD}"
git rev-parse -q --verify "$base^{commit}" >/dev/null 2>&1 || { echo "check-migrations: base $base không tồn tại — bỏ qua"; exit 0; }
FORBIDDEN='(\bDROP\b|\bRENAME\b|\bTRUNCATE\b|\bDELETE[[:space:]]+FROM\b|ALTER[[:space:]]+COLUMN[^;]*\bTYPE\b|SET[[:space:]]+NOT[[:space:]]+NULL)'
fail=0; n=0
while IFS=$'\t' read -r status path newpath; do
  [ -n "${status:-}" ] || continue
  n=$((n + 1))
  case "$status" in
    A)
      name="$(basename "$path")"
      if ! [[ "$name" =~ ^V[0-9]{12}__[a-z0-9_]+\.sql$ ]]; then
        echo "✗ $path: tên phải là V<yyyyMMddHHmm>__<slug>.sql (vd V$(date -u +%Y%m%d%H%M)__add_invoice.sql)"; fail=1
      fi
      body="$(git show "$head:$path" | sed -E 's/--.*$//')"
      if echo "$body" | grep -Eiq "$FORBIDDEN"; then
        if git show "$head:$path" | grep -q -- '-- dk:allow-destructive'; then
          echo "! $path có thao tác phá hủy, đã đánh dấu dk:allow-destructive — người review phải xác nhận"
        else
          echo "✗ $path chứa thao tác phá hủy (thêm cột/bảng mới thay vì sửa; nếu bắt buộc, thêm dòng '-- dk:allow-destructive <lý do>'):"
          echo "$body" | grep -Ein "$FORBIDDEN" | head -5; fail=1
        fi
      fi ;;
    R*) echo "✗ $path → $newpath: migration đã commit bị đổi tên"; fail=1 ;;
    *)  echo "✗ $path: migration đã commit bị sửa/xóa ($status) — tạo migration mới thay vì sửa"; fail=1 ;;
  esac
done < <(git diff --name-status -M "$base" "$head" -- "$DIR" | grep '\.sql' || true)
[ $fail -eq 0 ] && echo "✓ migration hợp lệ ($n thay đổi)"
exit $fail
