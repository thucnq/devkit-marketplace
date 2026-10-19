# Thiết kế: stack profile — dk 0.7.0 hỗ trợ Python / TypeScript / Cloudflare

> Trạng thái: **chờ duyệt** (chưa code). Ngày 2026-10-19. Động lực: dự án cá nhân Lẩu Meme (pipeline Python + Cloudflare Worker TypeScript + D1 + React/Vite).
> Ràng buộc cứng: dự án **không có** `.dk/stack.toml` (QLDN và mọi dự án java-spring) chạy **y hệt 0.6.1** — có test chứng minh.

## 1. Vấn đề

dk 0.6.1 viết cứng giả định Java ở 9 chỗ:

| Chỗ | Giả định cứng |
|---|---|
| `dk-check.sh` | `mvn -pl backend`, `npm --prefix frontend`, thư mục `backend/`, `frontend/` |
| `/dk:build` (SKILL.md) | `./mvnw … -Dtest='<Feature>*'`, Surefire |
| `dk-evidence.py` | đọc `surefire-reports/TEST-*.xml`, `@DisplayName` trong file `.java` |
| `ac-trace.py` | `TEST_GLOBS` chỉ gồm `backend/src/test/**/*.java`, `frontend/src/**/*.test.ts(x)` |
| `check-migrations.sh` | thư mục Flyway, tên `V<yyyyMMddHHmm>__` |
| `guard.py` | `PROD_CODE`, `TEST_WRITE_OK`, `TEST_READ_OK` theo `backend/`, `frontend/`; chặn né cổng kiểu Java/TS, không biết Python; không biết `.dev.vars`, `wrangler deploy` |
| `new-project.sh` | một golden path duy nhất (Spring) |
| `/dk:ship` + `deploy.sh` | Docker Compose qua SSH |
| `/dk:estimate`, `gen-plan.py` | luôn xuất báo giá; công suất = N kỹ sư × 8 giờ/ngày |

Agent `test-author`, `reviewer` và các skill quy ước cũng chỉ nói về Spring/React.

## 2. Ý tưởng chính

1. **Stack profile khai báo trong dự án**: `.dk/stack.toml` liệt kê các *thành phần* (component). Script đọc nó thay vì viết cứng Java. Thiếu file ⇒ profile ngầm định `java-spring` = đúng hành vi 0.6.1.
2. **Một định dạng kết quả test: JUnit XML.** Surefire, `pytest --junitxml`, vitest reporter `junit` đều xuất được. `dk-evidence.py` chỉ đọc một định dạng cho mọi ngôn ngữ.
3. **Một nơi đọc profile: `scripts/dk_stack.py`** (thư viện + CLI). Script bash gọi CLI, script Python import. Không ai tự parse `stack.toml`.

### Vì sao TOML, không YAML
Python ≥ 3.11 có `tomllib` sẵn trong thư viện chuẩn; YAML cần PyYAML (không chắc có trên máy/CI). Ubuntu 24.04 có Python 3.12. `/dk:doctor` kiểm Python ≥ 3.11 khi dự án có `stack.toml`. Hệ quả: tên file là `.dk/stack.toml` (prompt cũ ghi `stack.yml` — đổi có chủ đích).

## 3. Schema `.dk/stack.toml`

```toml
schema = 1
profile = "py-ts-cloudflare"          # nhãn; chỉ để hiển thị và chọn checklist review

[defaults]
ac_style = "both"                      # AC-X-NN trong tên test; Python cho phép thêm dạng ac_x_nn

[[component]]
name       = "pipeline"                # duy nhất; dùng trong báo cáo và dk-check
kind       = "python"                  # python | ts-worker | react-vite | java-maven | react-spring-fe
root       = "pipeline"                # thư mục gốc của thành phần
src_dirs   = ["pipeline/src"]          # code production — test-author KHÔNG đọc
test_dirs  = ["pipeline/tests"]        # test-author chỉ ghi ở đây
read_ok    = ["pipeline/pyproject.toml", "pipeline/tests/fixtures"]  # test-author được đọc thêm
# Các lệnh dưới chạy với cwd = root. Bỏ trống = dùng mặc định của kind (bảng mục 4).
format     = "ruff format --check ."
lint       = "ruff check ."
test       = "pytest -q --junitxml=../.dk/junit/pipeline.xml"
test_filter = "-k {feature_snake}"     # nối vào lệnh test khi /dk:build <feature>
junit      = ".dk/junit/pipeline.xml"  # đường dẫn từ gốc repo
coverage   = { cmd = "pytest -q --cov=src --cov-fail-under={min}", min = 80 }
build      = ""                        # rỗng = không có bước build
migration  = { kind = "none" }

[[component]]
name       = "worker"
kind       = "ts-worker"
root       = "worker"
src_dirs   = ["worker/src"]
test_dirs  = ["worker/test"]
read_ok    = ["worker/migrations", "worker/wrangler.jsonc", "worker/package.json"]
migration  = { kind = "wrangler-seq", dir = "worker/migrations" }
deploy     = { kind = "cloudflare", config = "worker/wrangler.jsonc", health = "/api/health",
               nonprod_envs = ["staging"], d1_binding = "DB" }

[[component]]
name       = "web"
kind       = "react-vite"
root       = "web"
src_dirs   = ["web/src"]
test_dirs  = ["web/src"]               # test nằm cạnh code: chỉ file *.test.ts(x) được ghi
test_glob  = "**/*.test.{ts,tsx}"
build      = "npm run -s build"
```

Quy tắc kiểm tra schema (`dk_stack.py validate`, chạy ở `session-start.sh`, lỗi thì in cảnh báo rõ ràng chứ không im lặng dùng mặc định):
- `schema = 1`; `name` duy nhất; `root` tồn tại; `src_dirs` và `test_dirs` nằm trong repo.
- `kind` thuộc danh sách; `migration.kind` ∈ {`none`, `flyway-ts`, `wrangler-seq`}; `deploy.kind` ∈ {`compose-ssh`, `cloudflare`}.
- Chỉ một thành phần có `deploy`. `nonprod_envs` không được chứa tên bắt đầu bằng `prod`.

### Profile ngầm định `java-spring` (khi không có file)
Tương đương:
```toml
[[component]]
name = "backend"; kind = "java-maven"; root = "."; src_dirs = ["backend/src/main/java"]
test_dirs = ["backend/src/test"]; migration = { kind = "flyway-ts", dir = "backend/src/main/resources/db/migration" }
deploy = { kind = "compose-ssh" }
[[component]]
name = "frontend"; kind = "react-spring-fe"; root = "frontend"; src_dirs = ["frontend/src"]; test_dirs = ["frontend/src"]
```
**Nhưng** khi không có file, `dk-check.sh` và `guard.py` vẫn chạy **nguyên nhánh code 0.6.1** (không đi qua profile). Lý do: bảo đảm QLDN không đổi dù chỉ một dòng báo cáo; nhánh profile chỉ dùng cho dự án mới. Khi đã ổn định (0.8.x) mới cân nhắc gộp.

## 4. Lệnh mặc định theo `kind`

| kind | format | lint | test (+JUnit) | test_filter | coverage mặc định | build |
|---|---|---|---|---|---|---|
| `python` | `ruff format --check .` | `ruff check .` | `pytest -q --junitxml=…` | `-k {feature_snake}` | `--cov-fail-under=80` | — |
| `ts-worker` | `npx prettier --check .` | `npm run -s lint` | `npx vitest run --reporter=default --reporter=junit --outputFile=…` | `-t {FEATURE}` | `--coverage` + ngưỡng 80 trong cấu hình vitest | `npx wrangler deploy --dry-run --outdir=.dk/tmp/wrangler` |
| `react-vite` | như trên | `npm run -s lint` + `npm run -s typecheck` | vitest như trên | `-t {FEATURE}` | 70 | `npm run -s build` |

`{feature_snake}` = `ac_ten_ma` dạng snake; `{FEATURE}` = Mã viết hoa (`GAME`). Lọc theo **Mã AC** chứ không theo tên lớp → tránh lỗi phân biệt hoa thường kiểu Surefire (bài học 0.6.0).

Mức chạy trong `dk-check.sh` (chỉ thành phần có file thay đổi; `full` chạy tất cả):

| Mode | python | ts-worker / react-vite |
|---|---|---|
| `precommit` | format + lint | lint (+ typecheck) |
| `precommit-strict` | + test (không coverage) | + test |
| `quick` | format + lint + test + coverage | lint + typecheck + test + coverage |
| `full` | quick + Semgrep `p/python` | quick + build + Semgrep `p/typescript` |

Các bước chung giữ nguyên: gitleaks, AC traceability, migration, OpenAPI lint (nếu có `docs/api/openapi.yaml`), osv-scanner (thêm `--lockfile` cho `uv.lock`/`requirements*.txt` và `package-lock.json` của từng thành phần).

## 5. Quy ước AC trong test (3 ngôn ngữ)

| Ngôn ngữ | Cách gắn AC | Ví dụ |
|---|---|---|
| Java | như cũ: tên method hoặc `@DisplayName("AC-…")` | `@DisplayName("AC-NOTE-01: …")` |
| Python | tên hàm `test_ac_<ma>_<nn>_<mo_ta>` **và** docstring bắt đầu bằng ID | `def test_ac_graph_01_doi_xung(): """AC-GRAPH-01: A+B = B+A"""` |
| TypeScript | tiêu đề `it`/`test` bắt đầu bằng ID | `it("AC-DISC-02: từ chối công thức giả", …)` |

- `dk_stack.ac_ids(text)` nhận cả `AC-X-NN` và (chỉ trong file `.py`) `ac_x_nn` → chuẩn hóa về `AC-X-NN`.
- `ac-trace.py`: `TEST_GLOBS` lấy từ profile (`test_dirs` + đuôi theo kind); giữ nguyên danh sách cũ khi không có profile.
- `dk-evidence.py`: đọc mọi file `junit` của profile (hoặc Surefire khi không có profile). Tên testcase của pytest là tên hàm, của vitest là tiêu đề đầy đủ → cùng hàm `ac_ids` lấy ra AC.
- Ngoài `-TENANT`, `-VALIDATION` (Java), dự án không có tenant dùng `-ABUSE` (giới hạn tần suất, đầu vào độc) — `implicit` như hai cái cũ.

## 6. Migration `wrangler-seq`

`check-migrations.sh` thêm tham số `--kind wrangler-seq --dir <dir>` (dk-check truyền từ profile; không tham số = Flyway như cũ, file trong template không đổi chữ ký).
- Tên: `^[0-9]{4}_[a-z0-9_]+\.sql$` (đúng định dạng `wrangler d1 migrations create` sinh ra — **cần kiểm tra lại** với wrangler bản đang dùng).
- Số mới phải **lớn hơn mọi số trên `base`** (hai nhánh cùng tạo `0004_` ⇒ đỏ). Dự án một người hiếm gặp, nhưng rẻ để chặn.
- Chỉ thêm; file đã commit không sửa/xóa/đổi tên; câu phá hủy cần `-- dk:allow-destructive <lý do>` — cùng luật Flyway. D1 là SQLite: thêm `DROP INDEX`, `ALTER TABLE … DROP COLUMN` vào danh sách phá hủy (đã có `DROP`).

## 7. `guard.py`

Khi có `stack.toml`:
1. **Phạm vi agent** dựng từ profile: `PROD_CODE` = mọi `src_dirs` trừ file khớp `test_glob`; `TEST_WRITE_OK` = `test_dirs` (+ `test_glob` khi test nằm cạnh code); `TEST_READ_OK` = `docs/`, `.dk/`, `test_dirs`, `read_ok`, thư mục migration. Không có profile ⇒ regex cũ y nguyên.
2. **Né cổng kiểu Python** (thêm vào `SUPPRESSIONS`, chỉ áp cho file `.py`): `@pytest.mark.skip`, `@pytest.mark.xfail`, `pytest.skip(`, `# noqa`, `# type: ignore`, `# pragma: no cover`. TS đã có `.skip/.only`, `@ts-ignore`, `@ts-expect-error`, `eslint-disable`; thêm `it.todo` không tính (không né được gì).
3. **File cấu hình chất lượng** thêm vào `QUALITY_FILES`: `ruff.toml`, `.ruff.toml`, `pytest.ini`, `.coveragerc`, `mypy.ini`, `vitest.config.*`, `vitest.workspace.*`.
4. **`pyproject.toml` không chặn cả file** (phải thêm được thư viện). Thay vào đó, như `pom.xml`: áp edit lên nội dung hiện tại → parse cũ/mới bằng `tomllib` → chặn nếu `[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.coverage]`, `[tool.mypy]` thay đổi, hoặc `fail_under` giảm. File không parse được sau edit ⇒ chặn (thông báo rõ).
5. **Bí mật**: thêm `.dev.vars`, `.dev.vars.<env>` (wrangler dùng cho biến bí mật cục bộ) vào `SECRET_PATH`; `.dev.vars.example` được phép.
6. **Production Cloudflare chỉ người làm** (cực kỳ quan trọng: `wrangler deploy` **không có `--env` là deploy production**):
   - Chặn `wrangler deploy|versions deploy|rollback|secret put|d1 migrations apply … --remote|d1 execute … --remote` khi **không** có `--env <x>` với `x ∈ nonprod_envs`.
   - Chặn `wrangler d1 time-travel restore` mọi lúc (khôi phục DB là việc của người).
   - `wrangler dev`, `--local`, `--dry-run` luôn được phép.
7. Tôn trọng `DK_ALLOW_QUALITY_EDIT=1` như cũ.

## 8. Golden path `py-ts-cloudflare`

`/dk:new-project <slug> --stack py-ts-cloudflare` → `new-project.sh` chọn `templates/py-ts-cloudflare/` (không đổi package Java; chỉ thay `goldenpath` → slug).

```
.dk/stack.toml                 # như mục 3
pipeline/                      # Python 3.12, uv (fallback pip), ruff, pytest, pytest-cov
  pyproject.toml  src/<slug_snake>_pipeline/__init__.py  tests/test_smoke.py
worker/                        # Cloudflare Worker TS + D1, phục vụ luôn web/dist (static assets)
  wrangler.jsonc  src/index.ts  test/health.test.ts  migrations/0001_init.sql
  package.json  tsconfig.json  eslint.config.js  vitest.config.ts
web/                           # React 19 + Vite + vitest + Testing Library
docs/  (brd, acceptance/, api/openapi.yaml, adr/0001-golden-path.md, input/README.md, runbook.md)
.github/workflows/ci.yml       # changes → lint/test từng thành phần, gitleaks CLI 8.30.1, ac-trace --started-only, check-migrations
.github/workflows/deploy-staging.yml   # thủ công (workflow_dispatch), dùng secret CLOUDFLARE_API_TOKEN
.githooks/pre-commit  .gitattributes (LF)  .gitignore  .gitleaks.toml  CLAUDE.md  README.md
.dev.vars.example
```

Quyết định cần duyệt:
- **Workers static assets thay cho Pages**: một Worker phục vụ cả SPA lẫn API ⇒ một lần deploy, một lệnh rollback, cùng origin (không CORS), có Cron Triggers nếu cần. Cloudflare hiện hướng dự án mới sang Workers (có hướng dẫn chuyển từ Pages) — **cần kiểm tra** giới hạn free tier hiện hành trước khi chốt.
- Test Worker bằng `@cloudflare/vitest-pool-workers` (chạy trong workerd với D1 cục bộ) — **cần kiểm tra** bản tương thích với vitest đang dùng.
- `.gitignore` sẵn: `.dk/log/.sessions/`, `.dk/junit/`, `.dk/tmp/`, `.dev.vars*` (trừ `.example`), `node_modules/`, `.venv/`, `.wrangler/`, `dist/`, `.claude/settings.local.json`.
- `.githooks/pre-commit` chặn thêm `.dev.vars*` (trừ `.example`).
- CI nằm trong hạn mức free; repo public ⇒ Actions không giới hạn phút (**cần kiểm tra** chính sách GitHub hiện hành).

## 9. Skill và agent

| Thành phần | Thay đổi |
|---|---|
| `/dk:new-project` | tham số `--stack java-spring|py-ts-cloudflare` (mặc định java-spring); bước build/test theo stack |
| `/dk:build` | lệnh RED/GREEN lấy từ `dk_stack.py test-cmd <feature>` (in lệnh của từng thành phần có AC của feature); bỏ ví dụ Maven cứng ra khỏi luồng chung, giữ trong phần "java-spring" |
| `/dk:design` | theo kind: Flyway (java) hoặc `worker/migrations/NNNN_*.sql` (D1, SQLite: `TEXT` cho id UUIDv7, `INTEGER` epoch ms cho thời gian, không RLS — cách ly bằng truy vấn); OpenAPI giữ nguyên |
| `/dk:review` | chọn checklist theo profile: thêm `skills/review/checklist-py-ts.md` (injection SQL trong D1 `prepare().bind()`, giới hạn tần suất, CORS, validate đầu vào, xử lý quota LLM, bí mật trong Actions, không đưa dữ liệu người chơi cho LLM) |
| `/dk:ship` | `deploy.kind = cloudflare` ⇒ `deploy-cf.sh` (mục 10); còn lại `deploy.sh` như cũ |
| `/dk:estimate --no-quote` | ghi `items.json` + chạy `gen-plan.py`; **không** chạy `gen-quote.py`, không hỏi đơn giá; bỏ mục cố định "Triển khai môi trường khách hàng", "Tài liệu bàn giao & đào tạo" |
| `/dk:plan` | thêm `--hours-per-week H` (lưu `params.hours_per_week`); `gen-plan.py`: thời lượng = `ceil(điểm × 8 / (H/5))` ngày làm việc mỗi làn. Không truyền ⇒ như cũ |
| `/dk:doctor` | kiểm theo profile: Python ≥ 3.11, `uv` hoặc `pip`, `ruff`, Node 22, `wrangler` (qua `npx`), đăng nhập `wrangler whoami` (chỉ WARN) |
| Skill quy ước mới | `python-conventions` (cấu trúc package, ruff, pytest, hàm thuần cho logic đồ thị, không gọi mạng trong unit test), `cf-worker-conventions` (Hono hoặc router tay, D1 `prepare/bind`, giới hạn tần suất, lỗi theo RFC 9457 như golden path Java) |
| `test-author` | thêm mục "Theo stack": đọc `.dk/stack.toml` để biết `test_dirs`, quy ước AC ở mục 5; Python: pytest + fixture từ `tests/fixtures/`; Worker: vitest-pool-workers gọi `SELF.fetch`; dữ liệu vàng ở `<test_dir>/golden/` |
| `reviewer` | đọc checklist theo profile |

## 10. `/dk:ship` cho Cloudflare — `scripts/deploy-cf.sh <env> [--rollback [version] | --releases | --url]`

1. Từ chối cây làm việc chưa commit; từ chối env không thuộc `nonprod_envs` (lớp thứ hai sau guard).
2. Build web, `npx wrangler d1 migrations apply <DB> --env <env> --remote` (migration chỉ thêm ⇒ code cũ vẫn chạy được trên schema mới, nên rollback code an toàn).
3. `npx wrangler deploy --env <env>`; lấy version id từ `npx wrangler deployments list --env <env> --json` (**cần kiểm tra** cờ `--json` với bản wrangler dùng).
4. Health: `GET <url><health>` 30 lần × 4 giây. Lỗi ⇒ `npx wrangler rollback <version trước> --env <env> -y` rồi dừng.
5. Ghi `.dk/releases/<env>.log` (thời điểm, git sha, version id) — commit cùng tài liệu.
- `--rollback [version]`: mặc định version liền trước trong log. Rollback chỉ đổi code; D1 không đổi (đúng với cách Cloudflare mô tả rollback). Khôi phục dữ liệu (D1 Time Travel) là việc của người, có trong runbook.
- Không làm k6 ở bản này; smoke = health + 1 request đọc (`GET /api/daily`). Thêm k6 sau nếu cần.
- Pipeline Python chạy bằng GitHub Actions cron trong repo dự án — không thuộc `ship`; `ship` chỉ nhắc nếu workflow cron chưa bật.

## 11. File phải sửa / thêm

**Thêm**: `scripts/dk_stack.py`, `scripts/deploy-cf.sh`, `templates/py-ts-cloudflare/**`, `skills/python-conventions/SKILL.md`, `skills/cf-worker-conventions/SKILL.md`, `skills/review/checklist-py-ts.md`, `tests/test_stack.py`, `tests/test_check.py`, `tests/fixtures/junit/{pytest,vitest,surefire}.xml`.
**Sửa**: `scripts/dk-check.sh`, `scripts/guard.py`, `scripts/ac-trace.py` (+ bản sao `templates/*/tools/`), `scripts/dk-evidence.py`, `scripts/check-migrations.sh` (+ bản sao), `scripts/new-project.sh`, `scripts/gen-plan.py`, `scripts/session-start.sh`, `scripts/wsl-doctor.sh`, `skills/{new-project,build,design,review,ship,estimate,plan,doctor}/SKILL.md`, `agents/{test-author,reviewer}.md`, `.claude-plugin/plugin.json` (0.7.0, mô tả không còn chỉ Java), `.github/workflows/golden-path.yml`, `README.md`, `docs/CHANGELOG` của plugin.
**Không sửa**: `templates/golden-path/**` ngoài bản sao `ac-trace.py`/`check-migrations.sh` (đồng bộ bằng `cmp` trong CI).

## 12. Rủi ro tương thích ngược

| Rủi ro | Giảm thiểu |
|---|---|
| Đổi `ac-trace.py`/`check-migrations.sh` làm QLDN đỏ | Không profile ⇒ đúng glob/thư mục cũ; test hồi quy chạy cả hai chế độ; tham số mới chỉ là tùy chọn |
| `dk-check.sh` đổi dòng báo cáo QLDN | Không profile ⇒ nhánh code 0.6.1 nguyên văn; test so sánh bảng kết quả của một repo java giả trước/sau |
| `guard.py` chặn nhầm dự án Java vì luật Python mới | Luật Python chỉ áp cho file `.py`/`pyproject.toml`; test cũ 19 cái phải xanh không sửa |
| `stack.toml` sai cú pháp làm cổng âm thầm tắt (bài học exit code ≠ 2) | Lỗi parse ⇒ guard **chặn** commit với thông báo sửa `stack.toml` (fail-closed), `dk-check` báo FAIL, `session-start` in cảnh báo |
| Python < 3.11 không có `tomllib` | `dk_stack.py` thử `tomllib` → `tomli`; không có cả hai ⇒ thông báo rõ; chỉ ảnh hưởng dự án có `stack.toml` |
| PR lớn khó review | Commit tách 4 phần (mục 14); mỗi commit xanh CI |

## 13. Kế hoạch test (tất cả chạy trong job `plugin`, < 5 phút)

1. `test_stack.py`: parse profile mẫu; validate lỗi (`name` trùng, `nonprod_envs` chứa `prod`, kind lạ); không file ⇒ java-spring; `ac_ids` nhận `AC-X-01`, `test_ac_x_01_y` (chỉ `.py`), không nhận `ac_x` trong file `.ts`.
2. `test_check.py`: repo giả có `stack.toml` với lệnh `true`/`false` ⇒ đúng thành phần chạy theo file thay đổi và mode; một thành phần đỏ ⇒ exit 1; **repo java giả không có `stack.toml` ⇒ bảng kết quả trùng khít với bản 0.6.1** (snapshot).
3. `test_guard.py` thêm: phạm vi test-author theo profile (đọc `pipeline/src` bị chặn, ghi `pipeline/tests` được), `@pytest.mark.skip`/`# noqa` bị chặn trong `.py` nhưng không chặn trong `.md`, `pyproject.toml` thêm dependency được / sửa `[tool.ruff]` bị chặn / hạ `fail_under` bị chặn, `.dev.vars` bị chặn, `wrangler deploy` không `--env` bị chặn, `--env staging` được, `d1 time-travel restore` bị chặn, `stack.toml` hỏng ⇒ chặn commit. 19 test cũ giữ nguyên, không sửa dòng nào.
4. `test_scripts.py` thêm: `dk-evidence` RED→GREEN từ fixture JUnit pytest và vitest; `check-migrations --kind wrangler-seq` (tên sai, số trùng, sửa file cũ, `DROP` không nhãn); `ac-trace` với test Python dạng `ac_x_nn`; `gen-plan --hours-per-week 20` ra lịch dài gấp 2 lần so với 1 kỹ sư toàn thời gian.
5. CI job mới `scaffold-py-ts` (~5 phút): `new-project.sh sample --stack py-ts-cloudflare` → `uv sync`/`pip install -e .[dev]` + `ruff` + `pytest`; `npm ci` + lint + vitest (worker, web); `npm run build` (web); `wrangler deploy --dry-run`; `ac-trace.py`; `dk-check.sh full` trên repo vừa dựng (công cụ thiếu ⇒ SKIPPED). Job `scaffold-and-build` (java) giữ nguyên.

## 14. Một PR, bốn commit

1. `feat(stack): dk_stack.py, stack.toml; dk-check, ac-trace, dk-evidence, check-migrations, guard đọc profile` + test.
2. `feat(stack): golden path py-ts-cloudflare, new-project --stack, doctor, skill quy ước, test-author/reviewer` + CI job.
3. `feat(plan): estimate --no-quote, plan --hours-per-week` + test.
4. `feat(ship): deploy-cf.sh, ship cho Cloudflare, chặn wrangler production` + test.

Version 0.7.0, CHANGELOG, README. Mô tả PR có mục **"Nâng cấp QLDN"**: không cần làm gì; chạy `/plugin marketplace update thuc-devkit`; kiểm bằng `dk-check.sh quick` trên qldn trước/sau và so bảng.

## 15. Câu hỏi cần duyệt

1. TOML (`.dk/stack.toml`) thay cho YAML — đồng ý?
2. Workers static assets thay cho Cloudflare Pages — đồng ý?
3. Khi không có profile, giữ nguyên nhánh code 0.6.1 (hai đường code song song một thời gian) thay vì ép java-spring đi qua profile — đồng ý?
4. Bỏ k6 khỏi `ship` Cloudflare ở bản này — đồng ý?
