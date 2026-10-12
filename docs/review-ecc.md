# Đối chiếu ECC (`affaan-m/ecc`) với plugin `dk` (2026-10-12)

ECC (bản 2.2.3) là bộ "hệ điều hành cho agent" dùng chung cho nhiều harness (Claude Code, Codex, Cursor, OpenCode…): khoảng 71 agent, 311 skill, 97 lệnh, cùng hook, rules, MCP config và installer. Phạm vi của nó rộng hơn dk rất nhiều. dk thì hẹp và chuyên: giao dự án freelance Java/Spring + React, cổng kiểm tra tất định, tiết kiệm token trên gói Pro.

**Kết luận:** không cài ECC trọn bộ cho repo dk, mà lấy những cơ chế **tất định, không tốn token** hợp với dk. Lý do:
- Nhiều hook chạy mỗi lượt tool, ví dụ GateGuard bắt agent "điều tra trước khi sửa".
- Quy trình plan/TDD riêng trùng với `/dk:*`.
- Continuous learning mang ngữ cảnh sang subagent.
- Tất cả những thứ trên làm tăng token và có thể phá tính độc lập của `test-author` / `reviewer`.

## Lấy vào dk (PR này)
| # | Ý tưởng từ ECC | Ở ECC | Cách áp dụng cho dk | Token |
|---|---|---|---|---|
| 1 | **Chặn agent nới cổng chất lượng**: agent hay sửa cấu hình linter để cho qua thay vì sửa code | hook `config-protection` (chặn sửa eslint/prettier/biome/ruff…) | `guard.py` chặn sửa eslint, prettier, tsconfig, SpotBugs/PMD, `.gitleaks.toml`, semgrep, CI workflow, `ArchitectureTest`, `ac-trace.py`, `check-migrations.sh`. Chặn thêm `@Disabled`, `NOPMD`, `@ts-ignore`, `eslint-disable`, `nosemgrep`, `gitleaks:allow`, `.skip/.only`. Chặn nới `pom.xml`: `skipTests`, `testFailureIgnore`, hạ `<minimum>` coverage. Người mở phiên `DK_ALLOW_QUALITY_EDIT=1` để sửa | 0 |
| 2 | **Bằng chứng RED → GREEN**: test chỉ viết mà chưa chạy đỏ thì không tính | skill `tdd-workflow` (RED gate, evidence report) | `dk-evidence.py red/green/report` đọc báo cáo Surefire, ánh xạ test sang AC qua `@DisplayName`. Ghi `.dk/evidence/<feature>.json` và cảnh báo AC đã xanh trước khi code (test không kiểm gì). Bảng RED → GREEN có trong PR | 0 |
| 3 | **Dấu hiệu bỏ dở**: "pre-existing", "flaky", "skip tests", "for now" | skill `delivery-gate` (regex trên câu trả lời cuối, chỉ cảnh báo) | Hook Stop (`dk-log.py`) nhận diện thêm cụm tiếng Việt ("lỗi có sẵn", "bỏ qua test", "để sau"…), báo cho người qua `systemMessage` và ghi vào log cho `/dk:retro`. Model không đọc thông báo này | 0 |
| 4 | **Nhắc compact theo kích thước ngữ cảnh**, không theo số lượt | hook `suggest-compact` (đọc `usage` trong transcript) | `dk-log.py` đọc ngữ cảnh thực từ transcript. Vượt `DK_COMPACT_AT` (mặc định 120k) thì nhắc người `/compact` hoặc `/clear`, nhắc lại mỗi 40k token tăng thêm | 0 |
| 5 | **Bài học tự nhắc lại ở phiên sau** | `continuous-learning-v2` (instinct, độ tin cậy, inject khi SessionStart) | Dạng nhẹ, do người chọn: `/dk:note #lesson …` → `session-start` in 5 bài học gần nhất. Không tự rút trích bằng LLM | ~100 token/phiên |
| 6 | **Checklist review Java** | agent `java-reviewer` | Thêm vào `reviewer`: SQL/JPQL nối chuỗi, `ORDER BY` không allow-list, command injection, path traversal, an toàn file upload Excel (giới hạn kích thước, zip-bomb và XXE của POI, kiểm tra magic bytes, CSV/Excel formula injection), `Optional.get()`, `@Modifying`, cascade, field injection | 0 (cùng lượt review) |
| 8 | **Hook có test hồi quy, chạy trong CI** | `tests/hooks/*.test.js`, CI validate hooks | `plugins/dk/tests/` (unittest, không phụ thuộc): 15 test cho `guard.py`, `dk-evidence.py`, `check-migrations.sh`, `ac-trace --started-only`, `gen-plan.py`; chạy trong job `plugin` của CI. Viết test đã lộ lỗi có sẵn: `guard.py` gọi `shutil.which` mà không import → cổng pre-commit chưa bao giờ chạy | 0 |
| 9 | **Phân tích lệnh shell theo đoạn**, không khớp chuỗi thô | `lib/shell-split`, `shell-substitution` | `guard.py` bỏ qua nội dung tin nhắn (`-m`, `--body`, `--title`, `echo`, heredoc vào lệnh không phải shell) khi tìm `git push`/`gh pr merge` → hết chặn nhầm commit/PR có nhắc tới các lệnh này; vẫn chặn `bash -c "git push origin main"` và heredoc vào `bash`. Lệnh shell ghi vào file cấu hình chất lượng (`sed -i`, `>`, `tee`, `cp/mv/rm`) bị chặn như Edit/Write | 0 |
| 7 | **Cách ly plugin cá nhân** | phần "data home"/isolation cho nhiều harness | `.claude/settings.local.json` (gitignore) cho plugin cá nhân, kèm danh sách plugin nên tắt trong repo dk (cũng là bài học trong runbook hopnhat 2.4) | – |

## Cân nhắc nhưng không lấy
| Ý tưởng ECC | Vì sao không |
|---|---|
| GateGuard (bắt trả lời câu hỏi sự thật trước mỗi lần sửa file hoặc chạy lệnh) | Thêm một lượt model cho mỗi file. dk đã có test-first và reviewer với context sạch |
| Continuous learning tự động (instinct sinh bằng LLM ở Stop hook) | Tốn token mỗi phiên, khó kiểm soát chất lượng. `/dk:note` + `/dk:retro` do người chọn rẻ và rõ ràng hơn |
| PreCompact gọi LLM tóm tắt phiên | Trạng thái dk đã nằm trong file (`.dk/state.md`, `docs/`, `docs/plan/`) nên compact không mất gì |
| Memory Vault chia sẻ giữa harness | Đội chỉ dùng Claude Code |
| Hook profile `minimal/standard/strict` + tắt hook theo ID | Hook dk gồm guard (an toàn, không được tắt) và log (rẻ). Không cần thêm lớp cấu hình |
| AgentShield quét `.claude/` | Dự án dk chỉ có `.claude/settings.json` sinh từ template. Đáng xem lại nếu bắt đầu nhận repo khách có sẵn cấu hình agent |
| 71 agent / 311 skill | Mỗi skill có mô tả thường trực trong ngữ cảnh. dk cố ý giữ ít skill và đặt `disable-model-invocation` |

## Có thể dùng như tài liệu tham khảo (không cài)
`springboot-security`, `springboot-verification`, `jpa-patterns`, `postgres-patterns`, `database-migrations` (expand-contract), `deployment-patterns` (rollback). Dùng khi viết backlog rollback cho `/dk:ship` và mã mẫu endpoint catalog.
