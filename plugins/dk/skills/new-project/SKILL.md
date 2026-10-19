---
name: new-project
description: Scaffold a new project from a golden path — java-spring (Spring Boot 3 + Java 21 + Postgres + React/Vite/Capacitor + Docker Compose) or py-ts-cloudflare (Python pipeline + Cloudflare Worker TypeScript + D1 + React/Vite).
argument-hint: <project-slug> [java.base.package] [--stack java-spring|py-ts-cloudflare]
arguments: [slug, package]
disable-model-invocation: true
allowed-tools: Bash, Read, Edit
---

Arguments: $ARGUMENTS

Stack: `py-ts-cloudflare` when the arguments contain `--stack py-ts-cloudflare` (or the user asked for Python/TypeScript/Cloudflare); otherwise `java-spring`.

### java-spring
Scaffold project `$slug` (base package: `$package`, default `vn.<slug without dashes>`).

1. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/new-project.sh" "$slug" "$package" "${user_config.marketplace_repo}"` from the parent directory the user is in. It copies the golden path, renames the package, sets up `.dk/state.md`, and runs `git init`.
2. `cd $slug` and run `./mvnw -q -DskipTests package` (use `mvn` if no wrapper was generated) and `npm --prefix frontend ci`. If either fails, fix the template issue — do not continue on a red build.
3. Ask the user ONE question: create the private GitHub repo now? If yes: `gh repo create $slug --private --source=. --push`.
4. Tell the user, in Vietnamese, in at most 5 lines: where the project is, how to run it locally (`docker compose -f deploy/compose.dev.yml up -d && ./mvnw -pl backend spring-boot:run`, `npm --prefix frontend run dev`), and that the next step is `/dk:spec <meeting notes>`.

### py-ts-cloudflare
1. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/new-project.sh" "$slug" "" "${user_config.marketplace_repo}" --stack py-ts-cloudflare` from the parent directory. It writes `.dk/stack.toml` (components pipeline / web / worker).
2. `cd $slug`, then: `uv sync --directory pipeline` (or `python3 -m venv pipeline/.venv && pipeline/.venv/bin/pip install -e pipeline pytest pytest-cov ruff`), `npm --prefix web ci`, `npm --prefix worker ci`, then `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-check.sh" full`. Every row must be PASS or SKIPPED (tool missing) — fix the template issue on any FAIL.
3. Ask ONE question: create the GitHub repo now, public or private? (Public = free Actions minutes for scheduled jobs; nothing secret may ever be committed.) If yes: `gh repo create $slug --public|--private --source=. --push`.
4. Reply in Vietnamese, max 6 lines: where the project is, how to run it (`docs/dev/setup.md`), that accounts and keys follow the project's account guide if the user has one, and that the next step is `/dk:spec docs/input/`.
