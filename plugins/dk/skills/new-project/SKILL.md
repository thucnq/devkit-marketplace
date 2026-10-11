---
name: new-project
description: Scaffold a new freelance project from the golden path (Spring Boot 3 + Java 21 + Postgres + React/Vite/Capacitor + Docker Compose + GitHub Actions).
argument-hint: <project-slug> [java.base.package]
arguments: [slug, package]
disable-model-invocation: true
allowed-tools: Bash, Read, Edit
---

Scaffold project `$slug` (base package: `$package`, default `vn.<slug without dashes>`).

1. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/new-project.sh" "$slug" "$package" "${user_config.marketplace_repo}"` from the parent directory the user is in. It copies the golden path, renames the package, sets up `.dk/state.md`, and runs `git init`.
2. `cd $slug` and run `./mvnw -q -DskipTests package` (use `mvn` if no wrapper was generated) and `npm --prefix frontend ci`. If either fails, fix the template issue — do not continue on a red build.
3. Ask the user ONE question: create the private GitHub repo now? If yes: `gh repo create $slug --private --source=. --push`.
4. Tell the user, in Vietnamese, in at most 5 lines: where the project is, how to run it locally (`docker compose -f deploy/compose.dev.yml up -d && ./mvnw -pl backend spring-boot:run`, `npm --prefix frontend run dev`), and that the next step is `/dk:spec <meeting notes>`.
