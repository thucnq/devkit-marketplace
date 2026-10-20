---
name: retro
description: End-of-project (or end-of-milestone) retrospective - turns the zero-token event log into a metrics report, then analyses it and proposes concrete improvements to the dk plugin.
argument-hint: "[điều bạn muốn tập trung phân tích]"
disable-model-invocation: true
allowed-tools: Read, Write, Bash
---

## Metrics (computed by script, not by you)
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk-report.py" .dk/retro || true`

Focus requested by the user: $ARGUMENTS

## Task
1. Read the newest `.dk/retro/*-report.md` (not the raw `.dk/log/*.jsonl` - too many tokens). Open `*-metrics.json` only for a number the report lacks.
2. Write `.dk/retro/<same date>-retro.md` in Vietnamese with exactly these sections:
   - **Tóm tắt** - 3 câu: dự án đi nhanh hay chậm so với ước lượng, chất lượng, chi phí token.
   - **Điều hiệu quả** - tối đa 5 gạch đầu dòng, mỗi dòng dẫn một con số trong báo cáo.
   - **Ma sát** - chỗ người phải can thiệp nhiều (prompt bổ sung cao), bước kiểm tra hay trượt, hook chặn lặp lại, lệnh tốn token bất thường, ghi chú #plugin.
   - **Đề xuất cải tiến plugin** - bảng `| Vấn đề | Bằng chứng (số liệu/ghi chú) | Thay đổi đề xuất | File trong plugin | Ưu tiên |`. Chỉ đề xuất có bằng chứng. File là đường dẫn trong plugin dk (ví dụ `skills/build/SKILL.md`, `agents/reviewer.md`, `scripts/guard.py`, `templates/golden-path/...`).
   - **Đề xuất cho golden path** - thành phần phải viết lại ở dự án này mà nên có sẵn từ đầu.
   - **Ước lượng** - các hạng mục lệch nhiều so với điểm ước lượng, và quy tắc ước lượng nên chỉnh trong `skills/estimate/SKILL.md`.
3. Do not change plugin files here - the plugin lives in its own repo. End by telling the user, in Vietnamese, in 2 lines: the file paths, and to bring `*-retro.md` + `*-metrics.json` to a Claude session opened on the plugin repo to implement the proposals.
