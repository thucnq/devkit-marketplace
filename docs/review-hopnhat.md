# Đối chiếu dự án `hopnhat` với plugin `dk` (2026-10-12)

`thucnq/hopnhat` cũng là cổng báo cáo cho chủ doanh nghiệp có nhiều công ty dùng MISA, nhưng được dựng theo kiểu khác: **pipeline 4 agent** (planner opus → developer sonnet → tester sonnet → reviewer opus) bàn giao cho nhau qua thư mục `pipeline/NNN-*/`, chạy liên tục bằng Remote Control trên một máy WSL luôn bật. Tính đến ngày review: 25 hạng mục, 11 hạng mục ở trạng thái HELD (đã lên staging, chờ người duyệt production), 1 hạng mục (nhập file MISA) bị BLOCKED vì thiếu file MISA mẫu + `expected.yaml` và chưa chốt bố cục cột.

## Ưu điểm và quyết định
| # | Ưu điểm của hopnhat | Quyết định cho dk | Ở đâu trong PR này |
|---|---|---|---|
| 1 | Chạy toàn bộ trong **WSL2**: `setup-windows.ps1`, `.gitattributes` ép LF, bootstrap báo lỗi khi repo ở `/mnt/c` hoặc file có CRLF | **Lấy**, mở rộng cho Windows 10 (fallback `dism`, `.wslconfig`, rule firewall) và hướng dẫn IntelliJ | `scripts/windows/setup-wsl.ps1`, `scripts/wsl-doctor.sh`, `/dk:doctor`, golden `.gitattributes`, `docs/dev/wsl-intellij.md` |
| 2 | Remote Control trong **tmux** + Task Scheduler tự chạy khi đăng nhập + `powercfg` chống ngủ | **Lấy**, tổng quát cho mọi dự án (tên phiên lấy từ `.dk/state.md`) | `scripts/dk-remote.sh`, `setup-wsl.ps1 -Configure` |
| 3 | **Migration chỉ thêm** (ADR-007) + `check-migrations.sh` cấm DROP/RENAME/đổi kiểu/SET NOT NULL | **Lấy**, thêm lối thoát `-- dk:allow-destructive <lý do>` do người xác nhận | `scripts/check-migrations.sh`, `dk-check.sh`, CI golden path |
| 4 | Tên migration theo **timestamp** `V202610011000__…` + `out-of-order: true` → 3 người làm song song không đụng số version | **Lấy** | `design`, `spring-conventions`, golden `application.yml`, kiểm trong `check-migrations.sh` |
| 5 | **Bất biến nghiệp vụ** (cân đối, cộng gộp, idempotent, thay thế phiên bản, khớp nguồn, truy vết, cách ly) chạy trên **dữ liệu vàng** tổng hợp (generator seed cố định + `expected.yaml` tính độc lập) | **Lấy** dạng quy ước: `AC-INV-NN`, `@Tag("invariant")`, `backend/src/test/resources/golden/` | `spec` (mục 2b), agent `test-author` |
| 6 | Test cách ly **fail-closed**: liệt kê mọi endpoint, endpoint mới chưa phân loại → đỏ | **Lấy** dạng hướng dẫn (chưa có code mẫu vì backend golden path chưa build được trong sandbox) | `security-baseline`, `test-author` |
| 7 | Mỗi hạng mục có **mức rủi ro** HIGH/MEDIUM/LOW quyết định độ kỹ của review | **Lấy**: `risk` trong `items.json` → Gantt và `/dk:review` | `items.schema.md`, `/dk:plan`, `review` |
| 8 | `BOARD.md` sinh tự động: trạng thái, số vòng test/review, phụ thuộc | **Lấy ý tưởng, đổi hình thức**: Gantt + checklist `docs/plan/` sinh từ báo giá, người tick tiến độ | `/dk:plan`, `gen-plan.py` |
| 9 | "Không đoán nghiệp vụ kế toán - ghi câu hỏi và dừng" | **Lấy** vào CLAUDE.md golden path | golden `CLAUDE.md` |
| 10 | Giới hạn vòng lặp (tester trả về tối đa 3, reviewer 2 → BLOCKED) | **Đã có** trong dk (`build` 6 vòng, `review` 3 vòng fix + 2 lần reviewer) | – |
| 11 | Phân quyền ghi file theo vai trò + commit identity riêng từng agent + CI `Guard` kiểm theo tác giả commit | **Chưa lấy**: dk chỉ có 3 agent và người merge; `guard.py` + cổng duyệt đã đủ. Xem lại nếu bật chế độ chạy tự động dài | backlog |
| 12 | Worktree riêng cho mỗi hạng mục (`.worktrees/NNN`), thư mục gốc luôn ở `main` | **Chưa lấy**: đội 3 người mỗi người một máy/nhánh. Hữu ích khi một máy chạy nhiều agent song song | backlog |
| 13 | Pipeline 4 agent tự chạy hết hàng đợi (`/pipeline`) | **Không lấy**: ngược nguyên tắc tiết kiệm token của dk (mỗi agent dựng lại context; planner + reviewer dùng opus). hopnhat cho thấy rủi ro: 11/25 hạng mục dồn ở HELD, 1 BLOCKED vì thiếu dữ liệu mẫu - cổng người duyệt mới là nút thắt, không phải tốc độ code | – |
| 14 | Observability đầy đủ (OTel collector, Prometheus, Grafana 3 dashboard, Alertmanager, Splunk) | **Chưa lấy**: vượt hạ tầng $0 của khách nhỏ. Có thể thêm profile `observability` tùy chọn cho golden path | backlog |
| 15 | `rollback.sh` + workflow `promote`/`rollback` theo image tag | **Nên lấy sau**: `/dk:ship` hiện chưa có rollback một lệnh | backlog (ưu tiên cao) |
| 16 | Thông báo Telegram khi BLOCKED/xong | **Không lấy**: app Claude đã có push notification cho Remote Control (`/config` → Push when actions required) | – |
| 17 | `PLAN.md` + `.plan-hash` để planner tự chạy lại khi yêu cầu đổi | **Đã có tương đương**: `dk-state.sh` đánh dấu contract `stale` khi spec đổi | – |

## Backlog đề xuất (theo thứ tự)
1. `/dk:ship rollback` + `deploy/rollback.sh` theo image tag (hopnhat #15).
2. Mã mẫu test endpoint catalog fail-closed trong golden path - viết khi CI golden path build được backend (hopnhat #6).
3. Generator dữ liệu vàng mẫu (Python, seed cố định) trong golden path cho dự án có import Excel (hopnhat #5).
4. Chế độ worktree cho một máy chạy nhiều phiên song song (hopnhat #12).
