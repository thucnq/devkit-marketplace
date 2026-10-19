#!/usr/bin/env bash
# Deterministic quality gates. Writes .dk/check-report.md. Exit 1 if any step FAILED.
# Modes: precommit | precommit-strict | quick | full
# Missing tools are SKIPPED (reported), never silently passed.
set -uo pipefail
MODE="${1:-quick}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p .dk
REPORT=".dk/check-report.md"
LOG="$(mktemp -d)"
RESULTS=()
FAILED=0

MVN="mvn"; [ -x ./mvnw ] && MVN="./mvnw"
has() { command -v "$1" >/dev/null 2>&1; }

run() { # run <name> <cmd...>
  local name="$1"; shift
  local out; out="$LOG/$(echo "$name" | tr ' /' '__').log"
  if "$@" >"$out" 2>&1; then
    RESULTS+=("| $name | PASS |")
  else
    RESULTS+=("| $name | **FAIL** |"); FAILED=1
    { echo; echo "### $name"; echo '```'; tail -40 "$out"; echo '```'; } >> "$LOG/failures.md"
  fi
}
skip() { RESULTS+=("| $1 | SKIPPED ($2) |"); }

staged() { git diff --cached --name-only --diff-filter=ACM 2>/dev/null; }
changed_since_main() { git diff --name-only "$(git merge-base HEAD origin/main 2>/dev/null || echo HEAD~1)" 2>/dev/null; }

# ---- secrets (all modes) ----
if has gitleaks; then
  case "$MODE" in
    precommit*) run "gitleaks (staged)" gitleaks protect --staged --redact --no-banner ;;
    *)          run "gitleaks" gitleaks detect --redact --no-banner --log-opts="$(git merge-base HEAD origin/main 2>/dev/null || git rev-list --max-parents=0 HEAD | tail -1)..HEAD" ;;
  esac
else
  # minimal fallback so secrets never pass silently
  pattern='(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|(password|secret|api[_-]?key)\s*[:=]\s*["'"'"'][^"'"'"'$\{ ]{8,})'
  case "$MODE" in precommit*) diff_src="git diff --cached -U0" ;; *) diff_src="git diff -U0 $(git merge-base HEAD origin/main 2>/dev/null || echo HEAD~1)" ;; esac
  if $diff_src 2>/dev/null | grep -E '^\+' | grep -Eiq "$pattern"; then
    RESULTS+=("| secret scan (fallback regex) | **FAIL** |"); FAILED=1
    { echo; echo "### secret scan"; echo "Staged diff matches a secret pattern. Install gitleaks for exact findings."; } >> "$LOG/failures.md"
  else
    RESULTS+=("| secret scan (fallback regex; install gitleaks) | PASS |")
  fi
fi

files="$( [ "${MODE#precommit}" != "$MODE" ] && staged || changed_since_main )"
touches_backend=$(echo "$files" | grep -qE '^(backend/|pom\.xml)' && echo 1 || echo 0)
touches_frontend=$(echo "$files" | grep -qE '^frontend/' && echo 1 || echo 0)
[ "$MODE" = full ] && touches_backend=1 && touches_frontend=1

# ---- backend ----
if [ -d backend ] && [ "$touches_backend" = 1 ]; then
  case "$MODE" in
    precommit)        run "backend compile" $MVN -q -B -pl backend -am compile ;;
    precommit-strict) run "backend unit + ArchUnit" $MVN -q -B -pl backend -am test -DexcludedGroups=api -Dspotless.check.skip=true ;;
    quick)            run "backend verify (tests, JaCoCo, ArchUnit)" $MVN -q -B -pl backend -am verify ;;
    full)             run "backend verify -Pquality (tests, JaCoCo, ArchUnit, Spotless, SpotBugs, PMD)" $MVN -q -B verify -Pquality ;;
  esac
fi

# ---- requirements traceability (project copy wins so CI and local agree) ----
TRACE="$HERE/ac-trace.py"; [ -f tools/ac-trace.py ] && TRACE="tools/ac-trace.py"
if [ -d docs/acceptance ] && [ "${MODE#precommit}" = "$MODE" ]; then
  feat="$(grep -E '^feature:' .dk/state.md 2>/dev/null | sed 's/feature:[[:space:]]*//')"
  if [ "$MODE" = quick ] && [ -n "$feat" ]; then
    run "AC traceability ($feat)" python3 "$TRACE" --feature "$feat"
  else
    run "AC traceability (all)" python3 "$TRACE"
  fi
fi

# ---- migrations: expand-only, committed ones untouched, timestamp names ----
if [ -d backend/src/main/resources/db/migration ] && [ "${MODE#precommit}" = "$MODE" ]; then
  MIG="$HERE/check-migrations.sh"; [ -f tools/check-migrations.sh ] && MIG="tools/check-migrations.sh"
  run "migrations (expand-only)" bash "$MIG"
fi

# ---- contract ----
if [ -f docs/api/openapi.yaml ] && [ "$MODE" = full ]; then
  if has npx; then run "OpenAPI lint" npx -y @redocly/cli@1 lint --format=stylish docs/api/openapi.yaml
  else skip "OpenAPI lint" "npx not found"; fi
fi

# ---- SAST & dependencies (full only) ----
if [ "$MODE" = full ]; then
  if has semgrep; then run "Semgrep" semgrep scan --error --quiet --config p/java --config p/react --config p/secrets --config p/owasp-top-ten
  else skip "Semgrep" "pip install semgrep"; fi
  if has osv-scanner; then run "osv-scanner (vulnerable deps)" osv-scanner scan source -r --lockfile=frontend/package-lock.json --lockfile=pom.xml .
  else skip "osv-scanner" "go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest"; fi
fi

# ---- frontend ----
if [ -f frontend/package.json ] && [ "$touches_frontend" = 1 ]; then
  if [ ! -d frontend/node_modules ]; then skip "frontend" "run npm --prefix frontend ci"
  else
    run "frontend typecheck" npm --prefix frontend run -s typecheck
    case "$MODE" in
      quick|full)
        run "frontend lint" npm --prefix frontend run -s lint
        run "frontend test" npm --prefix frontend run -s test -- --run ;;
    esac
    [ "$MODE" = full ] && run "frontend build" npm --prefix frontend run -s build
  fi
fi

{
  echo "$([ $FAILED = 0 ] && echo PASS || echo FAIL) · $MODE · $(date '+%F %T') · $(git rev-parse --short HEAD 2>/dev/null)"
  echo
  echo "| Check | Result |"
  echo "|---|---|"
  printf '%s\n' "${RESULTS[@]}"
  [ -f "$LOG/failures.md" ] && { echo; echo "## Failures"; cat "$LOG/failures.md"; }
} > "$REPORT"
cat "$REPORT"
failed="$(printf '%s\n' "${RESULTS[@]}" | grep -F '**FAIL**' | sed -E 's/^\| ([^|]+) \|.*/\1/' | sed 's/ *$//' | paste -sd ';' -)"
skipped="$(printf '%s\n' "${RESULTS[@]}" | grep -F 'SKIPPED' | sed -E 's/^\| ([^|]+) \|.*/\1/' | sed 's/ *$//' | paste -sd ';' -)"
python3 "$HERE/dk_event.py" check mode="$MODE" result="$([ $FAILED = 0 ] && echo PASS || echo FAIL)" failed="$failed" skipped="$skipped" >/dev/null 2>&1 || true
rm -rf "$LOG"
exit $FAILED
