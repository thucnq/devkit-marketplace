---
name: estimate
description: Build the work breakdown and the client quote (.xlsx, same layout as the QLDN quote) from the BRD and acceptance criteria.
argument-hint: "[notes: rate, team size, infra option, payment terms]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

## Scope
!`grep -h "^### AC-" docs/acceptance/*.md 2>/dev/null | wc -l | xargs echo "Total ACs:"`
!`grep -c "Bắt buộc" docs/acceptance/*.md 2>/dev/null || true`

Extra instructions from the user: $ARGUMENTS

## Quoted scope (if any)
!`ls docs/input/ 2>/dev/null | grep -iE "hang-muc|bao-gia|quote" || echo "không có file báo giá trong docs/input/"`

## Task
1. Read `docs/scope.md`, `docs/brd.md` and `docs/acceptance/*.md`. One estimate item per feature Mã in `docs/scope.md` (name it after the feature, put the Mã and AC range in `desc`). Also fill the scheduling fields `id` (= Mã), `deps`, `ac`, `risk` described in the schema — `/dk:plan` uses them for the Gantt chart.
2. Write `docs/estimate/items.json` following `${CLAUDE_PLUGIN_ROOT}/skills/estimate/items.schema.md`. Estimation rules:
   - 1 point = 1 engineer-day for a mid-level engineer WITH this golden path (auth, tenant, audit, CI, deploy already exist → do not price them again, except a fixed "Khởi tạo dự án & hạ tầng" item of 3 points).
   - Price per feature from its ACs: ~0.5 point per simple AC (CRUD/validation), 1–2 per AC with business rules, 3–5 for integrations, imports, reports, or anything with an external system. Round each item to 0.5.
   - Always add items: "Kiểm thử nghiệm thu & sửa lỗi" (15% of feature points), "Tài liệu bàn giao & đào tạo" (2–3 points), "Triển khai môi trường khách hàng" (2 points).
   - Sensitive personal data (biometric, health, CCCD scans): add "Tuân thủ dữ liệu cá nhân nhạy cảm" (consent flow, encryption, DPIA hồ sơ đánh giá tác động) 3–5 points.
   - Mark optional items `"optional": true` — they go orange in the sheet.
   - Every assumption that changes price → `"open": true` with the question; they go yellow and into the "Câu hỏi cần chốt" sheet.
3. Fill `params` from the user's instructions; otherwise leave defaults (hourly rate and overhead come from plugin config: rate=${user_config.hourly_rate_vnd}, overhead=${user_config.overhead_pct}%; if these still read as literal placeholders, the plugin is not configured — keep the schema defaults and say so).
4. If an earlier quote exists in `docs/input/` (item list or total points): write `docs/estimate/doi-chieu-bao-gia.md` — table `| Hạng mục báo giá | Điểm đã báo | Tính năng (Mã) | Điểm ước lượng mới | Chênh lệch |` plus rows for features with no quoted item ("Ngoài báo giá") and quoted items with no feature, then the totals. This is for the human to decide whether to cut scope or renegotiate — never change a signed quote yourself.
5. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gen-quote.py" docs/estimate/items.json docs/estimate/bao-gia.xlsx`.
6. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gen-plan.py"` (schedule + Gantt; it prints `thiếu`/errors only if items.json is malformed — fix and re-run).
7. Reply in Vietnamese, max 9 lines, copying the numbers from the script's summary lines (never compute totals yourself): points, build cost, months, infra options, number of open questions, path to the file, and — if step 4 ran — the total difference versus the earlier quote in one line; one line from gen-plan (planned acceptance date, `docs/plan/gantt.html`) and suggest `/dk:plan bắt đầu YYYY-MM-DD` once the start date and team are known. Do NOT paste the sheet contents.
