#!/usr/bin/env bash
# PostToolUse formatter: formats only the edited file, only if a formatter is available. Never fails the tool call.
f="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("tool_input") or {}).get("file_path",""))' 2>/dev/null)"
[ -n "$f" ] && [ -f "$f" ] || exit 0
case "$f" in
  *.java)
    if command -v google-java-format >/dev/null 2>&1; then google-java-format -r "$f" 2>/dev/null; fi ;;
  *.ts|*.tsx|*.js|*.jsx|*.css|*.json|*.md|*.yaml|*.yml)
    root="$(git -C "$(dirname "$f")" rev-parse --show-toplevel 2>/dev/null)"
    p="$root/frontend/node_modules/.bin/prettier"
    [ -x "$p" ] && "$p" --write --log-level silent "$f" 2>/dev/null ;;
esac
exit 0
