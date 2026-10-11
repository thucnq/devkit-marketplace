# thuc-devkit — plugin `dk` (Delivery Kit) cho Claude Code

Quy trình giao dự án freelance Java 21 / Spring Boot + Postgres + React với **3 agent**, **10 lệnh**, và **cổng kiểm soát tất định không tốn token**.

> Nguyên tắc: agent sinh ra → máy kiểm chứng → người quyết định. Người chỉ duyệt 3 cổng: chốt spec, chốt contract, merge.

## Cài đặt (mỗi thành viên, một lần)

```bash
# 1. Đẩy repo này lên GitHub (private), ví dụ thuc/devkit-marketplace
# 2. Trong Claude Code:
/plugin marketplace add thuc/devkit-marketplace
/plugin install dk@thuc-devkit
/plugin configure dk@thuc-devkit     # đơn giá/giờ, % overhead, marketplace_repo = thuc/devkit-marketplace
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
| `/dk:estimate` | Chia việc → báo giá theo mẫu QLDN | `docs/estimate/bao-gia.xlsx` | – |
| `/dk:design` | Schema, OpenAPI, sơ đồ, ADR | migration, `openapi.yaml`, `*.mmd`, `adr/` | ✋ `/dk:approve contract` |
| `/dk:build <feature>` | `test-author` viết test trước (không nhìn code) → implement đến khi xanh | code + test | – |
| `/dk:review` | Mọi kiểm tra tất định → `reviewer` độc lập → mở PR kèm bảng truy vết AC | PR | ✋ người merge |
| `/dk:ship [env]` | Deploy non-prod qua SSH, k6 theo NFR, kiểm tra backup phục hồi được, `doc-sync` | URL staging, tài liệu cập nhật | – |
| `/dk:note #tag nội dung` | Ghi nhận xét ngay khi gặp vấn đề (tag gợi ý: #spec #build #review #plugin #token #khach) | `.dk/log/` | – |
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
| Mọi AC bắt buộc có test | `ac-trace.py` (hook trước commit, CI) | 0 |
| Cách ly tenant | Postgres RLS + test `AC-*-TENANT` bắt buộc | 0 |
| Kiến trúc | ArchUnit | 0 |
| Bí mật không lọt | gitleaks / regex trong hook commit; hook chặn agent đọc `.env` | 0 |
| Production chỉ người làm | Hook chặn lệnh deploy/ssh tới host prod, `gh pr merge`, push main | 0 |
| Không sửa migration đã commit | Hook | 0 |
| Hiệu năng | k6 thresholds trong `/dk:ship` | 0 |
| Lỗ hổng phụ thuộc, SAST | osv-scanner, Semgrep, SpotBugs, PMD | 0 |
| Lỗi logic, PII, phân quyền | Agent `reviewer` (ngữ cảnh sạch) | có |

## Tiết kiệm token (gói Pro)
- Lệnh workflow đặt `disable-model-invocation` → mô tả không nằm thường trực trong ngữ cảnh.
- Skill kiến thức chỉ nạp khi chạm `backend/**` hoặc `frontend/**`.
- Trạng thái dự án được bơm vào bằng `!command` (chạy trước khi Claude đọc), không tốn lượt gọi tool.
- `doc-sync` chạy Haiku; ERD và tổng tiền báo giá do script tính.
- Mỗi giai đoạn để lại file → `/clear` thoải mái giữa các giai đoạn.

Đo thử trên brief "báo cáo vân tay" (Sonnet, tính theo giá API để so sánh): `/dk:spec` 9 lượt ≈ $0.77, `/dk:estimate` 6 lượt ≈ $0.27.

## Trạng thái kiểm chứng (v0.2.0)
- ✅ `claude plugin validate --strict` (plugin + marketplace), cài đặt và chạy `/dk:approve`, `/dk:spec`, `/dk:estimate` thật trong Claude Code 2.1.292.
- ✅ Hook guard: 30 tình huống chặn/cho phép; hook commit chặn bí mật.
- ✅ Log: ghi đúng lệnh, prompt (chỉ đếm), tool, hook chặn, kiểm tra, cổng, verdict reviewer, token không đếm trùng; `/dk:note` và `/dk:retro` chạy thật.
- ✅ Báo giá: công thức tái tạo đúng từng số của file QLDN mẫu (609.700.000 / 616.700.000 …), 0 lỗi công thức.
- ✅ Frontend golden path: typecheck, lint, 6 test, build.
- ⚠️ **Backend golden path chưa được biên dịch** (môi trường dựng không truy cập được Maven Central). Mã đã qua google-java-format (parse OK). Workflow `.github/workflows/golden-path.yml` sẽ build + test toàn bộ ở lần push đầu tiên — sửa đỏ trước khi dùng cho khách.
- ⚠️ `/dk:build`, `/dk:review`, `/dk:ship` chưa chạy thật (cần Maven/Docker).

## Cấu trúc
```
plugins/dk/
  agents/      test-author (Sonnet), reviewer (Sonnet, read-only), doc-sync (Haiku)
  skills/      8 lệnh workflow + 4 skill kiến thức (security-baseline, vn-data-protection, spring/react-conventions)
  hooks/       guard (Bash + file), format, session-start
  scripts/     dk-state, dk-check, ac-trace, gen-erd, gen-quote, new-project, deploy
  templates/golden-path/   dự án mẫu đầy đủ
```
