# thuc-devkit - plugin `dk` (Delivery Kit) cho Claude Code

Quy trình giao dự án với **3 agent**, **12 lệnh**, và **cổng kiểm soát tất định không tốn token**. Hai golden path: **java-spring** (Java 21 / Spring Boot + Postgres + React, dự án freelance) và **py-ts-cloudflare** (pipeline Python + Cloudflare Worker TypeScript + D1 + React, từ 0.7.0).

> Nguyên tắc: agent sinh ra → máy kiểm chứng → người quyết định. Người chỉ duyệt 3 cổng: chốt spec, chốt contract, merge.

## Môi trường: WSL2 Ubuntu (khuyến nghị cho máy Windows 10/11)

Claude Code, agent, hook, Maven, Docker chạy **trong WSL2**; Windows chỉ chạy IntelliJ và trình duyệt. Chạy trực tiếp trên Windows (Git Bash) gây lỗi CRLF, mất quyền thực thi, hook chạy sai - phiên dk sẽ cảnh báo khi phát hiện.

1. PowerShell (Admin): `plugins/dk/scripts/windows/setup-wsl.ps1 -Drive D` - cài WSL2 + Ubuntu 24.04 vào ổ D (bỏ `-Drive` thì script hỏi chọn ổ; Ubuntu đã ở ổ C thì lệnh này chuyển sang D), ghi `.wslconfig`.
2. Trong Ubuntu: cài công cụ, Claude Code, clone repo vào `~/` (không đặt ở `/mnt/c`), chạy `/dk:doctor`.
3. IntelliJ: mở project qua `\\wsl$`, JDK của WSL, cấu hình chạy/debug có sẵn trong `.run/`.
4. (Tùy chọn) `setup-wsl.ps1 -Configure`: Remote Control tự chạy trong tmux khi đăng nhập Windows.

Chi tiết từng bước và xử lý sự cố: [`plugins/dk/templates/golden-path/docs/dev/wsl-intellij.md`](plugins/dk/templates/golden-path/docs/dev/wsl-intellij.md) (được chép vào mọi dự án mới).

## Cài đặt (mỗi thành viên, một lần)

```bash
# 1. Repo marketplace: thucnq/devkit-marketplace
# 2. Trong Claude Code:
/plugin marketplace add thucnq/devkit-marketplace
/plugin install dk@thuc-devkit
/plugin configure dk@thuc-devkit     # đơn giá/giờ, % overhead, marketplace_repo mặc định thucnq/devkit-marketplace
```

Công cụ nên có trên máy (thiếu thì kiểm tra tương ứng báo SKIPPED, không im lặng cho qua):
`java 21`, `maven`, `docker`, `node 22`, `python3` + `pip install openpyxl`, `gh`, `gitleaks`, `semgrep`, `osv-scanner`, `k6`.

Dự án tạo bằng `/dk:new-project` có sẵn `.claude/settings.json` tự bật plugin cho cả nhóm.

## Quy trình

| Lệnh | Việc | Đầu ra | Cổng |
|---|---|---|---|
| `/dk:new-project <slug> [--stack py-ts-cloudflare]` | Sinh dự án từ golden path (mặc định java-spring) | Repo chạy được, CI, deploy, `.dk/stack.toml` (py-ts) | – |
| `/dk:spec docs/input/` (lần 1) | Ghi chú họp/chat → **đề xuất danh sách tính năng**, có nguồn trích dẫn, cỡ S/M/L, đối chiếu báo giá nếu có | `docs/scope.md` | ✋ bạn sửa và đổi Trạng thái thành *Đã chốt* |
| `/dk:spec docs/input/` (lần 2) | Phạm vi đã chốt → BRD, tiêu chí nghiệm thu, câu hỏi cho khách | `docs/brd.md`, `docs/acceptance/*.md`, `docs/open-questions.md` | ✋ `/dk:approve spec` |
| `/dk:estimate [--no-quote]` | Chia việc → báo giá theo mẫu QLDN, kèm lịch sơ bộ (`--no-quote`: dự án cá nhân, chỉ điểm và lịch) | `docs/estimate/bao-gia.xlsx`, `docs/plan/*` | – |
| `/dk:plan [bắt đầu YYYY-MM-DD] [--hours-per-week H]` | Lịch theo phụ thuộc + **Gantt** + **checklist tiến độ** (người tick hạng mục/AC, % , ngày thực tế; chạy lại để tính dự báo trễ) | `docs/plan/gantt.html` (offline, có nút tải checklist), `gantt.md` (Mermaid trên GitHub), `tien-do.md` | – |
| `/dk:design` | Schema, OpenAPI, sơ đồ, ADR | migration, `openapi.yaml`, `*.mmd`, `adr/` | ✋ `/dk:approve contract` |
| `/dk:build <feature>` | `test-author` viết test trước (không nhìn code) → implement đến khi xanh | code + test | – |
| `/dk:review` | Mọi kiểm tra tất định → `reviewer` độc lập → mở PR kèm bảng truy vết AC | PR | ✋ người merge |
| `/dk:ship [env]` | Deploy non-prod: qua SSH + k6 + kiểm tra backup (java-spring) hoặc Cloudflare Workers + D1 + health + tự rollback (py-ts-cloudflare), rồi `doc-sync` | URL staging, tài liệu cập nhật | – |
| `/dk:note #tag nội dung` | Ghi nhận xét ngay khi gặp vấn đề (tag gợi ý: #spec #build #review #plugin #token #khach) | `.dk/log/` | – |
| `/dk:doctor [--fix]` | Kiểm tra máy: WSL2, repo ngoài `/mnt/c`, LF, Java 21, Docker, Node 22, gh, Claude Code | báo cáo OK/WARN/FAIL | – |
| `/dk:retro` | Cuối dự án/mốc: số liệu từ log → phân tích → đề xuất cải tiến plugin | `.dk/retro/<ngày>-report.md`, `-metrics.json`, `-retro.md` | – |

## Log để cải tiến plugin sau mỗi dự án

Hook ghi log tự động, **không tốn token**, vào `.dk/log/<tên-git>.jsonl` (mỗi người một file nên không xung đột khi merge; commit cùng dự án):

| Ghi gì | Không ghi gì |
|---|---|
| Lệnh `/dk:*` nào chạy, khi nào, ai chạy · số prompt bổ sung của người (đếm, không lưu nội dung) · tool đã gọi (lệnh Bash cắt 120 ký tự và che bí mật, đường dẫn file) · tool lỗi · hook chặn gì · kết quả từng bước kiểm tra · cổng duyệt · verdict và số blocker của reviewer · token theo model và theo lệnh (đọc từ transcript) · ghi chú `/dk:note` | Nội dung prompt · nội dung file · output của tool · giá trị bí mật |

Sau dự án: chạy `/dk:retro`, rồi mang `*-retro.md` + `*-metrics.json` vào một phiên Claude mở trên repo plugin này để triển khai đề xuất. Không muốn commit log thì thêm `.dk/log/` vào `.gitignore`.

## Bảo đảm FR / NFR bằng máy, không bằng lời hứa của agent

| Yêu cầu | Cơ chế | Tốn token |
|---|---|---|
| Mọi AC bắt buộc có test | `ac-trace.py` (CI: `--started-only` - chỉ tính năng đã bắt đầu build; `dk-check full`: java mọi AC, stack profile tính năng của nhánh + `--started-only`) | 0 |
| Cách ly tenant | Postgres RLS + test `AC-*-TENANT` bắt buộc | 0 |
| Kiến trúc | ArchUnit | 0 |
| Bí mật không lọt | gitleaks / regex trong hook commit; hook chặn agent đọc `.env` | 0 |
| Production chỉ người làm | Hook chặn lệnh deploy/ssh tới host prod, `gh pr merge`, push main | 0 |
| Không sửa migration đã commit; migration chỉ thêm, tên theo timestamp | Hook + `check-migrations.sh` (dk-check, CI) | 0 |
| Bất biến nghiệp vụ (cân đối, cộng gộp, idempotent…) | `AC-INV-*` trên dữ liệu vàng, `@Tag("invariant")` | 0 |
| Hiệu năng | k6 thresholds trong `/dk:ship` | 0 |
| Lỗ hổng phụ thuộc, SAST | osv-scanner, Semgrep, SpotBugs, PMD | 0 |
| Agent không nới cổng để cho qua (sửa eslint/tsconfig/SpotBugs/PMD/gitleaks/CI, thêm `@Disabled`, `NOPMD`, `@ts-ignore`, hạ coverage) | Hook `guard.py`; người mở phiên `DK_ALLOW_QUALITY_EDIT=1` khi cần đổi luật | 0 |
| Test được viết trước và từng đỏ | `dk-evidence.py` RED → GREEN theo AC (Surefire), bảng trong PR | 0 |
| Lỗi logic, PII, phân quyền | Agent `reviewer` (ngữ cảnh sạch) | có |

## Tiết kiệm token (gói Pro)
- Lệnh workflow đặt `disable-model-invocation` → mô tả không nằm thường trực trong ngữ cảnh.
- Skill kiến thức chỉ nạp khi chạm `backend/**` hoặc `frontend/**`.
- Trạng thái dự án được bơm vào bằng `!command` (chạy trước khi Claude đọc), không tốn lượt gọi tool.
- `doc-sync` chạy Haiku; ERD và tổng tiền báo giá do script tính.
- Mỗi giai đoạn để lại file → `/clear` thoải mái giữa các giai đoạn.

Đo thử trên brief "báo cáo vân tay" (Sonnet, tính theo giá API để so sánh): `/dk:spec` 9 lượt ≈ $0.77, `/dk:estimate` 6 lượt ≈ $0.27.

## Thay đổi v0.7.6 - chỉ ra việc bỏ dở kèm bằng chứng
Ở lau-meme, "tiếp tục việc đang dở" sau `/clear` buộc agent tự lục log mới biết nhánh `feat/feedback` có 4 commit đã push mà chưa có PR và lần `/dk:review` trước dừng ở check FAIL; PR #135 cũng được merge trong khi 2 commit sửa workflow còn nằm lại trên nhánh, làm `main` đỏ mà không ai thấy.
- `scripts/dk-unfinished.py` (không tốn token, chỉ đọc git và `.dk/`, < 1 s): in từng dấu hiệu bỏ dở kèm bằng chứng. Các dấu hiệu: thay đổi chưa commit ngoài `.dk/`; nhánh còn commit chưa vào nhánh chính (chưa push, đã push mà chưa merge, hoặc PR đã merge nhưng còn commit đến sau; commit đã cherry-pick sang nhánh chính không tính); lần `dk-check` gần nhất FAIL (kèm dòng đầu báo cáo và các dòng đỏ, cảnh báo khi HEAD đã đổi); có RED mà chưa có GREEN; file spec/contract đổi sau khi duyệt cổng; `/dk:review` đã bắt đầu mà nhánh chưa `review-<nhánh>: approved`. Nhánh không có commit trong 14 ngày bị bỏ qua (`--days`).
- `session-start.sh` chạy script này, nên đầu mỗi phiên (kể cả sau `/clear`) có mục "Dấu hiệu việc bỏ dở" với bằng chứng.
- `CLAUDE.md` mẫu của hai golden path thêm quy tắc "Unfinished work": khi nói việc nào bỏ dở hoặc được yêu cầu làm tiếp, agent dựa vào các dòng này và trích đúng bằng chứng (nhánh, commit, dòng báo cáo check, thời điểm trong log), không đoán theo trí nhớ. Dự án cũ: chép dòng "Unfinished work" trong `templates/<stack>/CLAUDE.md` vào `CLAUDE.md` của dự án.

## Thay đổi v0.7.5 - bài học từ log lau-meme (19-26/10/2026)
Số liệu từ `/dk:retro` của lau-meme: 9.667 sự kiện, 58 phiên, 1,45 tỷ token, hook chặn 295 lần.
- **Guard không còn chặn nhầm test-author** (195 lần `agent_blind`, ~90% là nhầm, nên test của nó luôn tới tay mà chưa chạy). Lệnh shell được tách theo nháy và theo `cd`: `cd worker`, `npm --prefix worker run test | tail`, `uv run --directory pipeline pytest`, `ls web/src`, mẫu tìm của grep/sed, `find -name '*.test.*'`, `grep --include=*.test.ts` đều được phép; đọc file production hay grep cả thư mục `src` vẫn bị chặn. Chạy lại 234 lệnh thật từng bị chặn: 223 nay qua, 11 còn lại là chặn đúng.
- Test setup nằm cạnh code (`web/src/test/setup.ts`, `__mocks__/`) là phần của test, test-author đọc/ghi được. Đường dẫn trong worktree (`../app-fix`, `.claude/worktrees/x`) được so với `.dk/` của chính worktree đó.
- `>` trong chuỗi nháy (awk `$2 >= 3`, thân heredoc python) không còn bị coi là ghi file; `sed -i 's/a/b/; s/c/d/'` không bị cắt ở `;`; `cd x && cat >> test.py` tính theo thư mục sau `cd`. Force-push chỉ xét đúng lệnh `git push` (văn bản nhắc `git push` cạnh `gh api -f` không còn bị chặn).
- `dk-check full` có stack profile: AC traceability = tính năng của nhánh (đủ mọi AC) + các tính năng đã bắt đầu (`--started-only`, giống CI). Trước đây cổng này đỏ 29/31 lần ở `/dk:review` vì tính năng đã spec trên main nhưng đang build ở nhánh khác, khiến agent quen bỏ qua dòng đỏ. Dự án Java giữ nguyên như 0.6.1.
- `/dk:review`: chạy `dk-check full` ở nền song song với reviewer, mở PR ngay khi APPROVE (sửa lỗi check sau bằng commit tiếp theo); PR luôn `--base main`; `gh pr edit` hỏng do GitHub bỏ Projects (classic) thì dùng `gh api -X PATCH`. `/dk:build`: đưa test-author giao diện cần gọi, tự chạy typecheck/lint/test trước RED, chỉ chạy bộ test đã lọc theo tính năng.
- Golden path py-ts-cloudflare: `testTimeout: 30_000` cho worker và web (Miniflare D1 ~66 ms/truy vấn trên WSL, 110 lần quá hạn 5 s), `.prettierrc.json` cho web/worker theo đúng style (không có file này `prettier --write` đổi cả file sang dấu nháy kép), `.dk/log/*.jsonl merge=union` trong `.gitattributes` (log không còn xung đột khi gộp nhánh). Dự án cũ: chép ba thay đổi này vào dự án.
- Golden path Java: ghim Testcontainers 1.21.4 (Spring Boot 3.5.6 kèm 1.21.3 gọi Docker API 1.32, Docker mới trên runner GitHub đòi ≥ 1.40 nên mọi test tích hợp lỗi "Could not find a valid Docker environment"). Dự án cũ: thêm `<testcontainers.version>1.21.4</testcontainers.version>` vào `pom.xml` gốc.
- `dk-report.py`: liệt kê lỗi tool hay gặp nhất (thay vì 3 mẫu đầu tiên), hook chặn theo subagent, số dòng log hỏng; đếm cả lần chạy `pytest`.

## Thay đổi v0.7.4
- Task nền chạy quá 10 phút phải được đánh giá lại, không được lặng lẽ chờ tiếp. Agent kiểm tiến trình còn sống không, output còn tăng không, lần trước lệnh đó mất bao lâu, rồi báo người dùng một dòng: vẫn chạy bình thường (dự kiến xong lúc nào) hoặc bị treo (dừng, chạy lại hẹp hơn). Quy tắc nằm trong `/dk:build`, `/dk:review`, `/dk:ship` và `CLAUDE.md` mẫu của hai golden path. Dự án cũ: chép dòng "Background tasks" trong `templates/<stack>/CLAUDE.md` vào `CLAUDE.md` của dự án.

## Thay đổi v0.7.3
- Guard chặn vòng chờ `until/while ... pgrep -f ...` (luật `pgrep_wait`): `pgrep -f` khớp với chính dòng lệnh `bash -c` của vòng lặp nên vòng không bao giờ dừng. Ở lau-meme, một lần RED chạy 1,5 phút đã để người dùng chờ 5 giờ. `/dk:build` và `/dk:review` hướng dẫn chạy thẳng lệnh test/check ở chế độ nền và chờ thông báo.

## Thay đổi v0.7.2
- `ac-trace.py --started-only` (cổng CI): AC thêm sau vào file nghiệm thu đã bắt đầu mà `docs/estimate/items.json` ghi id cụ thể chỉ dưới hạng mục chưa bắt đầu thì báo `planned (not enforced yet)`, không làm đỏ CI. Hạng mục coi là đã bắt đầu khi có AC chỉ riêng nó ghi id cụ thể đã có test; tiền tố như `AC-ART` không tính là lịch. `/dk:review` và `/dk:ship` vẫn đòi đủ mọi AC. Dự án cũ: chép lại `templates/<stack>/tools/ac-trace.py` vào `tools/`.
- `ac-trace.py` chạy được trên Windows (không có `SIGPIPE`).

## Thay đổi v0.7.1
- `dk-state.sh require`: sửa lỗi thoát mã 1 khi spec không đổi sau khi duyệt (làm `/dk:design`, `/dk:build` dừng dù cổng đã duyệt) và lỗi cú pháp thiếu `fi` của bản vá trước.

## Thay đổi v0.7.0 - stack profile (Python / TypeScript / Cloudflare)
Thiết kế: [`docs/design/stack-profile.md`](docs/design/stack-profile.md).
- `.dk/stack.toml` khai báo thành phần (`python`, `ts-worker`, `react-vite`, `java-maven`); `scripts/dk_stack.py` là nơi duy nhất đọc nó. **Dự án không có file này (QLDN và mọi dự án java-spring) chạy y như 0.6.1** - test so bảng kết quả `dk-check` với bản 0.6.1 đóng băng.
- `dk-check.sh`, `ac-trace.py`, `dk-evidence.py` (JUnit XML chung cho Surefire/pytest/vitest), `check-migrations.sh --kind wrangler-seq`, `/dk:build`, `/dk:design`, `/dk:review` theo profile. Test Python gắn AC bằng tên `test_ac_<ma>_<nn>_…`.
- Guard: phạm vi `test-author` theo profile; chặn `# noqa`, `# type: ignore`, `pytest.mark.skip/xfail`, `pragma: no cover`; `pyproject.toml` chỉ chặn `[tool.ruff|pytest|coverage|mypy]`; `.dev.vars` là bí mật; **`wrangler deploy/rollback/secret put/d1 … --remote` không có `--env <nonprod>` bị chặn** (top-level là production); profile hỏng ⇒ chặn commit và agent.
- Golden path `py-ts-cloudflare`: Worker phục vụ cả API lẫn web tĩnh (Workers static assets), D1, `@cloudflare/vitest-plugin`, pipeline Python (uv, ruff, pytest), CI + workflow deploy có cổng người cho production. Skill `python-conventions`, `cf-worker-conventions`, checklist review py-ts.
- `/dk:ship` Cloudflare: `deploy-cf.sh` (migrate D1, deploy `--env`, health, tự rollback, `.dk/releases/<env>.log`, `--rollback`). `/dk:estimate --no-quote`, `/dk:plan --hours-per-week`. `/dk:doctor` theo stack.
- **Nâng cấp QLDN**: không cần làm gì ngoài `/plugin marketplace update thuc-devkit`.

## Thay đổi v0.6.1
- `setup-wsl.ps1`: chọn ổ đĩa cho Ubuntu khi cài (`-Drive D`, `-InstallDir`, hoặc hỏi kèm dung lượng trống từng ổ), chuyển Ubuntu đang ở C sang ổ khác (`wsl --manage --move`, WSL cũ thì export/import an toàn), đặt `swapFile` cùng ổ, `-Status`. Test PowerShell (`plugins/dk/tests/test_setup_wsl.ps1`) chạy trong CI.
- `/dk:doctor` cảnh báo khi ổ C còn ít chỗ.

## Thay đổi v0.6.0
- **Tính độc lập của agent do hook bảo đảm**, không chỉ nằm trong prompt: `test-author` không đọc được code production (Read/Grep/Bash) và chỉ ghi file test; `reviewer` chỉ ghi `.dk/reviews/`, không chạy lệnh git đổi cây làm việc; `doc-sync` chỉ sửa tài liệu.
- Guard chặn thêm việc sửa `.dk/state.md` và migration đã commit **qua lệnh shell** (`echo >>`, `sed -i`).
- `/dk:ship`: `deploy.sh` từ chối cây làm việc chưa commit, ghi `releases.log` trên máy chủ, `--rollback [tag]` và `--releases`; health lỗi thì quay lại bản trước.
- Golden path có git hook `pre-commit` cho người (quét bí mật, chặn commit dữ liệu khách / file env); `/dk:new-project` tự bật, `/dk:doctor` nhắc clone chưa bật.
- `/dk:build` lọc test đúng tên lớp (`-Dtest='<Feature>*'`, Surefire phân biệt hoa thường).
- `marketplace_repo` mặc định `thucnq/devkit-marketplace` (trước là `OWNER/…`, dự án mới không tự cài được plugin cho đồng đội).
- CI plugin chạy shellcheck + pyflakes; 19 test hồi quy.

## Thay đổi v0.5.0
- Từ ECC (xem [`docs/review-ecc.md`](docs/review-ecc.md)): chặn agent nới cổng chất lượng và thêm suppression; bằng chứng RED → GREEN theo AC; cảnh báo câu trả lời có dấu hiệu bỏ dở và nhắc `/compact` khi ngữ cảnh lớn (hiện cho người, model không tốn token); `/dk:note #lesson` nhắc lại ở đầu phiên; checklist review injection và upload Excel.
- Test hồi quy cho hook và script (`plugins/dk/tests/`, chạy trong CI). Sửa lỗi cổng pre-commit không chạy (thiếu `import shutil`) và lỗi chặn nhầm khi commit message/PR body nhắc tới `git push`/`gh pr merge`.
- Từ runbook hopnhat: tác vụ Windows giữ WSL sống (`exec sleep infinity`), `dk-remote` tự chạy lại khi mất mạng, `setup-wsl.ps1` kiểm ảo hóa + `-MoveTo` ổ khác, `/dk:doctor` báo Docker Desktop lẫn vào PATH và biến môi trường chặn Remote Control, plugin cá nhân để ở `.claude/settings.local.json`.

## Thay đổi v0.4.0
- WSL2 + IntelliJ: `setup-wsl.ps1`, `/dk:doctor`, `dk-remote.sh`, `.gitattributes`, `.run/` (chạy/attach debug), `scripts/dev/debug-api.sh`, cảnh báo khi phiên chạy trên Git Bash hoặc `/mnt/c`.
- `/dk:plan`: Gantt + checklist tiến độ sinh từ báo giá (`gen-plan.py`, không tốn token); `/dk:estimate` tự chạy lần đầu.
- Từ `hopnhat` (xem [`docs/review-hopnhat.md`](docs/review-hopnhat.md)): migration chỉ thêm + tên timestamp, bất biến nghiệp vụ trên dữ liệu vàng, test endpoint fail-closed, rủi ro theo hạng mục.
- Sửa 2 lỗi CI đã gặp ở QLDN: `ac-trace --started-only` cho CI; `.dk/log/.sessions/` vào allowlist gitleaks.

## Trạng thái kiểm chứng (v0.7.0)
| Phần | Trạng thái | Bằng chứng |
|---|---|---|
| Manifest plugin + marketplace | ✅ | `claude plugin validate --strict` |
| Hook guard, dk-evidence, check-migrations, ac-trace, gen-plan, rollback | ✅ | `plugins/dk/tests/` (19 test cũ + 29 test stack profile) chạy trong job `plugin` của CI |
| Golden path py-ts-cloudflare | ✅ | job `scaffold-py-ts`: dựng dự án, `dk-check full` không FAIL, ac-trace, dk-evidence |
| `deploy-cf.sh` với Cloudflare thật | ⚠️ chưa | test dùng `wrangler`/`curl` giả; cần một lần deploy staging thật |
| Golden path backend + frontend | ✅ | job `scaffold-and-build`: dựng dự án như `/dk:new-project`, `mvn verify -Pquality` (Testcontainers), typecheck/lint/test/build |
| Báo giá | ✅ | công thức tái tạo đúng file QLDN mẫu (609.700.000 / 616.700.000 …) |
| `/dk:spec`, `/dk:estimate`, `/dk:approve` | ✅ | chạy thật trên QLDN |
| Cổng pre-commit | ⚠️ | chỉ chạy đúng từ 0.5.0 (trước đó hook lỗi `shutil` nên không chặn gì) |
| `/dk:build`, `/dk:review`, `/dk:ship`, `dk-evidence` trên dự án thật | ⚠️ chưa | QLDN mới tới phase design |
| `setup-wsl.ps1`, `.run/` IntelliJ | ⚠️ chưa | cần thử trên Windows 10 / IntelliJ thật |

## Cấu trúc
```
plugins/dk/
  agents/      test-author (Sonnet), reviewer (Sonnet, read-only), doc-sync (Haiku)
  skills/      10 lệnh workflow + 6 skill kiến thức (security-baseline, vn-data-protection, spring/react/python/cf-worker-conventions)
  hooks/       guard (Bash + file), format, session-start
  scripts/     dk-state, dk-check, ac-trace, check-migrations, gen-erd, gen-quote, gen-plan (+ gantt-template.html),
               new-project, deploy, deploy-cf, dk_stack, dk-remote, wsl-doctor, windows/setup-wsl.ps1
  templates/golden-path/        dự án mẫu java-spring
  templates/py-ts-cloudflare/   dự án mẫu Python + Cloudflare Worker + D1 + React
```
