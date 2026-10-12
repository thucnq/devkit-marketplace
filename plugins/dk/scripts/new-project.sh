#!/usr/bin/env bash
# Scaffold a project from the golden path. Usage: new-project.sh <slug> [base.package] [marketplace owner/repo]
set -euo pipefail
SLUG="${1:?usage: new-project.sh <slug> [base.package]}"
[[ "$SLUG" =~ ^[a-z][a-z0-9-]{1,40}$ ]] || { echo "slug must be lowercase kebab-case"; exit 1; }
PKG="${2:-}"; [ -z "$PKG" ] && PKG="vn.$(echo "$SLUG" | tr -d '-')"
MARKET="${3:-OWNER/devkit-marketplace}"
[[ "$PKG" =~ ^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$ ]] || { echo "invalid java package: $PKG"; exit 1; }
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../templates/golden-path" && pwd)"
[ -e "$SLUG" ] && { echo "$SLUG already exists"; exit 1; }

cp -R "$SRC" "$SLUG"
cd "$SLUG"
rm -rf frontend/node_modules frontend/dist backend/target

# rename java package directories
OLD_PATH="vn/goldenpath"; NEW_PATH="$(echo "$PKG" | tr . /)"
for root in backend/src/main/java backend/src/test/java; do
  if [ -d "$root/$OLD_PATH" ]; then
    mkdir -p "$root/$NEW_PATH.tmp" && cp -R "$root/$OLD_PATH/." "$root/$NEW_PATH.tmp/"
    rm -rf "$root/vn/goldenpath"; rmdir "$root/vn" 2>/dev/null || true
    mkdir -p "$(dirname "$root/$NEW_PATH")" && mv "$root/$NEW_PATH.tmp" "$root/$NEW_PATH"
  fi
done

# database identifiers cannot comfortably contain dashes
DBID="$(echo "$SLUG" | tr '-' '_')"
for f in deploy/compose.dev.yml backend/src/main/resources/application.yml backend/src/main/resources/application-dev.yml; do
  sed -e "s/goldenpath/$DBID/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

# replace identifiers in text files (portable sed -i)
LC_ALL=C grep -rIl --exclude-dir=.git --exclude-dir=node_modules -e 'vn\.goldenpath' -e 'goldenpath' . | while read -r f; do
  sed -e "s/vn\.goldenpath/$PKG/g" -e "s/goldenpath/$SLUG/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
sed -e "s#__MARKETPLACE_REPO__#$MARKET#" .claude/settings.json > .claude/settings.json.tmp && mv .claude/settings.json.tmp .claude/settings.json
chmod +x deploy/*.sh scripts/dev/*.sh tools/*.sh 2>/dev/null || true

# maven wrapper (generated locally so the project pins its Maven version)
if command -v mvn >/dev/null 2>&1; then
  mvn -q -N wrapper:wrapper -Dtype=only-script -Dmaven=3.9.11 || echo "WARN: could not generate mvnw; use mvn"
fi

git init -q -b main
mkdir -p .dk
printf '# dk state (managed by dk-state.sh — do not edit)\nphase: spec\nproject: %s\npackage: %s\n' "$SLUG" "$PKG" > .dk/state.md
git add -A && git commit -q -m "chore: scaffold from dk golden path" && echo "✅ $SLUG created (package $PKG)"
