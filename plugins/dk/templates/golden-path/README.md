# goldenpath

Khởi tạo từ golden path của plugin `dk`. Xem `CLAUDE.md` cho quy trình và `docs/runbook.md` cho vận hành.

```bash
docker compose -f deploy/compose.dev.yml up -d     # Postgres cho môi trường dev
./mvnw -pl backend spring-boot:run                 # API: http://localhost:8080
npm --prefix frontend ci && npm --prefix frontend run dev   # Web: http://localhost:5173
```
Debug bằng IntelliJ (Windows + WSL2): xem `docs/dev/wsl-intellij.md`. Tiến độ: `docs/plan/gantt.html` (sinh bởi `/dk:plan`).

Tài khoản dev: `admin@demo.local` / `Demo@12345`.
