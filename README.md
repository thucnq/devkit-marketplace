# thuc-devkit — plugin `dk` (Delivery Kit) cho Claude Code

Quy trình giao dự án freelance Java 21 / Spring Boot + Postgres + React với **3 agent**, **12 lệnh**, và **cổng kiểm soát tất định không tốn token**.

> Nguyên tắc: agent sinh ra → máy kiểm chứng → người quyết định. Người chỉ duyệt 3 cổng: chốt spec, chốt contract, merge.

## Môi trường: WSL2 Ubuntu (khuyến nghị cho máy Windows 10/11)

Claude Code, agent, hook, Maven, Docker chạy **trong WSL2**; Windows chỉ chạy IntelliJ và trình duyệt. Chạy trực tiếp trên Windows (Git Bash) gây lỗi CRLF, mất quyền thực thi, hook chạy sai — phiên dk sẽ cảnh báo khi phát hiện.

1. PowerShell (Admin): `plugins/dk/scripts/windows/setup-wsl.ps1` — cài WSL2 + Ubuntu 24.04, ghi `.wslconfig`.
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
| `/dk:new-project <slug>` | Sinh dự án từ golden path | Repo chạy được, CI, deploy | – |
| `/dk:spec docs/input/` (lần 1) | Ghi chú họp/chat → **đề xuất danh sách tính năng**, có nguồn trích dẫn, cỡ S/M/L, đối chiếu báo giá nếu có | `docs/scope.md` | ✋ bạn sửa và đổi Trạng thái thành *Đã chốt* |
| `/dk:spec docs/input/` (lần 2) | Phạm vi đã chốt → BRD, tiêu chí nghiệm thu, câu hỏi cho khách | `docs/brd.md`, `docs/acceptance/*.md`, `docs/open-questions.md` | ✋ `/dk:approve spec` |
| `/dk:estimate` | Chia việc → báo giá theo mẫu QLDN, kèm lịch sơ bộ | `docs/estimate/bao-gia.xlsx`, `docs/plan/*` | – |
| `/dk:plan [bắt đầu YYYY-MM-DD]` | Lịch theo phụ thuộc + **Gantt** + **checklist tiến độ** (người tick hạng mục/AC, % , ngày thực tế; chạy lại để tính dự báo trễ) | `docs/plan/gantt.html` (offline, có nút tải checklist), `gantt.md` (Mermaid trên GitHub), `tien-do.md` | – |
| `/dk:design` | Schema, OpenAPI, sơ đồ, ADR | migration, `openapi.yaml`, `*.mmd`, `adr/` | ✋ `/dk:approve contract` |
| `/dk:build <feature>` | `test-author` viết test trước (không nhìn code) → implement đến khi xanh | code + test | – |
| `/dk:review` | Mọi kiểm tra tất định → `reviewer` độc lập → mở PR kèm bảng truy vết AC | PR | ✋ người merge |
| `/dk:ship [env]` | Deploy non-prod qua SSH, k6 theo NFR, kiểm tra backup phục hồi được, `doc-sync` | URL staging, tài liệu cập nhật | – |
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
| Mọi AC bắt buộc có test | `ac-trace.py` (review/ship: mọi AC; CI: `--started-only` — chỉ tính năng đã bắt đầu build) | 0 |
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

## Trạng thái kiểm chứng (v0.6.0)
| Phần | Trạng thái | Bằng chứng |
|---|---|---|
| Manifest plugin + marketplace | ✅ | `claude plugin validate --strict` |
| Hook guard, dk-evidence, check-migrations, ac-trace, gen-plan, rollback | ✅ | `plugins/dk/tests/` (19 test) chạy trong job `plugin` của CI |
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
  skills/      10 lệnh workflow + 4 skill kiến thức (security-baseline, vn-data-protection, spring/react-conventions)
  hooks/       guard (Bash + file), format, session-start
  scripts/     dk-state, dk-check, ac-trace, check-migrations, gen-erd, gen-quote, gen-plan (+ gantt-template.html),
               new-project, deploy, dk-remote, wsl-doctor, windows/setup-wsl.ps1
  templates/golden-path/   dự án mẫu đầy đủ
```
