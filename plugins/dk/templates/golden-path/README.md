# goldenpath

Khởi tạo từ golden path của plugin `dk`. Xem `CLAUDE.md` cho quy trình và `docs/runbook.md` cho vận hành.

```bash
docker compose -f deploy/compose.dev.yml up -d     # Postgres cho môi trường dev
./mvnw -pl backend spring-boot:run                 # API: http://localhost:8080
npm --prefix frontend ci && npm --prefix frontend run dev   # Web: http://localhost:5173
```
Tài khoản dev: `admin@demo.local` / `Demo@12345`.
