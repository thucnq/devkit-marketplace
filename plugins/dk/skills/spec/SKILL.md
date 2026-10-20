---
name: spec
description: Turn raw client input (chat logs, call notes, meeting notes) into a proposed scope, then - once the human confirms the scope - a Vietnamese BRD, testable acceptance criteria, and open questions for the client.
argument-hint: "<path to notes or a folder like docs/input/, or paste notes> [bỏ qua phạm vi]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Bash
---

## Current state
!`cat .dk/state.md 2>/dev/null || echo "no .dk/state.md - run /dk:new-project first or create it"`

## Existing spec files
!`ls docs/scope.md docs/brd.md docs/acceptance/ docs/open-questions.md 2>/dev/null || true`

## Scope status
!`grep -m1 -E "^> Trạng thái:" docs/scope.md 2>/dev/null || echo "docs/scope.md chưa có"`

## Input files
!`ls -la docs/input/ 2>/dev/null || echo "docs/input/ chưa có"`

## Input
$ARGUMENTS

If the input names files or a folder that do not exist (see listing above), STOP and tell the user in Vietnamese exactly which files to add to `docs/input/` (see `docs/input/README.md`). Do not write a spec from guesses. Only meeting notes (or pasted notes) are required; a quote item list (`hang-muc.csv` or similar) is optional.

## Which step to run
- **Step A - propose scope** when `docs/scope.md` does not exist, or its status line is not `> Trạng thái: Đã chốt`, unless the input says `bỏ qua phạm vi`. Step A is cheap on purpose: the human trims the scope before you spend tokens on acceptance criteria.
- **Existing projects**: if `docs/scope.md` is absent but `docs/brd.md` already lists features (section 3 has rows), the project predates the scope step. Do not redo it: write `docs/scope.md` from the BRD feature list with `> Trạng thái: Đã chốt (tạo từ BRD hiện có)`, fill the quote column if a quote list exists, then run Step B in merge mode only if the input asks for changes; otherwise stop and report.
- **Step B - full spec** when `docs/scope.md` says `> Trạng thái: Đã chốt`, or the input says `bỏ qua phạm vi` (then run A and B in one go, and set the status to `Đã chốt (bỏ qua bước duyệt riêng)`).

---

## Step A - `docs/scope.md` (then STOP)
Read every file in the input. Derive the features the client needs - including the ones a senior BA knows they will need but did not say (login/roles, data import, audit, admin screens, reports they mentioned in passing). Do not pad: each feature must trace to something in the input or to a stated constraint.

Write `docs/scope.md` exactly in this shape (Vietnamese):

```
# Phạm vi đề xuất - <tên dự án>

> Trạng thái: Nháp - sửa trực tiếp file này (xóa dòng, đổi Ưu tiên, thêm ghi chú), rồi đổi thành "Đã chốt" và chạy lại /dk:spec
> Nguồn: <danh sách file đã đọc>

| Mã | Tính năng | Mô tả ngắn | Nguồn | Ưu tiên | Cỡ | Hạng mục báo giá |
|---|---|---|---|---|---|---|
| COMPANY | Quản lý đa công ty | … | ghi-chu-hop.md: "chuyển đổi nhanh giữa các công ty" | Bắt buộc | M | <tên hạng mục khớp, hoặc "-"> |

## Có sẵn trong golden path (không tính điểm)
Đăng nhập email/Google, phân quyền vai trò, cách ly dữ liệu theo tenant, audit log, CI/CD, triển khai Docker - chỉ liệt kê những gì dự án này cần.

## Đối chiếu báo giá
(chỉ khi có danh sách hạng mục báo giá hoặc tổng điểm đã báo)

## Cần hỏi trước khi chốt phạm vi
Tối đa 5 câu, chỉ những câu làm thay đổi danh sách tính năng.
```

Rules:
- **Mã**: UPPERCASE, 3–10 chars; it becomes the `AC-<MÃ>-NN` prefix and the `docs/acceptance/<mã-thường>.md` file name.
- **Nguồn**: quote the input (file + a few words), or `suy luận: <lý do>` for features the client did not state. The human uses this column to cut what they did not ask for.
- **Ưu tiên**: Bắt buộc | Tùy chọn. **Cỡ**: S (≤ 3 ngày công), M (4–10), L (> 10) - rough, for trimming only; real points come from `/dk:estimate`.
- **Hạng mục báo giá** - look for a quote item list in the input (`hang-muc.csv`, `*.xlsx`/`*.csv` with item names, or a quote summary with a points total):
  - If an item list exists: map every feature to an item; in "Đối chiếu báo giá" list (1) features with no matching item → **"Ngoài báo giá"** and (2) quote items no feature covers → **"Đã báo giá nhưng chưa có tính năng"**.
  - If only a total exists (e.g. "335 điểm bắt buộc"): sum the size midpoints (S=2, M=7, L=15) of mandatory features and say whether scope looks under, near, or over the quoted total. Say plainly this is a rough check.
  - If nothing exists: write "Chưa có báo giá - chạy /dk:estimate sau khi chốt phạm vi."
- Personal data: if a feature handles sensitive data per `${CLAUDE_PLUGIN_ROOT}/skills/vn-data-protection/SKILL.md`, say so in its Mô tả.

Finish Step A: `git add docs/scope.md && git commit -m "spec: đề xuất phạm vi"`, set state via `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" set spec scope-draft`, then reply in Vietnamese, max 8 lines: number of features (bắt buộc/tùy chọn), how many are `suy luận`, the quote comparison result in one line, and: "Sửa `docs/scope.md` (xóa/đổi ưu tiên), đổi Trạng thái thành **Đã chốt**, rồi chạy lại `/dk:spec`." **STOP - do not write the BRD or acceptance criteria in Step A.**

---

## Step B - full spec from the confirmed scope
Client input is always thin: a few headline features. Your value is the gap analysis a senior BA would do. Build only the features listed in `docs/scope.md` (respect the human's edits: removed rows are out of scope, keep their Mã and Ưu tiên). Produce, all in Vietnamese:

### 1. `docs/brd.md` - follow `${CLAUDE_PLUGIN_ROOT}/skills/spec/brd-template.md` exactly
If the file exists, merge: keep approved sections, mark changes with `(cập nhật <date>)`. Section 3 (Danh sách tính năng) must match `docs/scope.md` row for row.

### 2. `docs/acceptance/<feature-slug>.md` - one file per feature in scope
Format each criterion as:
```
### AC-<FEAT>-<NN>: <tên ngắn>
- **Cho** <bối cảnh / dữ liệu sẵn có>
- **Khi** <hành động>
- **Thì** <kết quả quan sát được: HTTP status, dữ liệu, thông báo, bản ghi audit>
- Ưu tiên: Bắt buộc | Tùy chọn
```
FEAT is the Mã from `docs/scope.md`. Rules:
- Every criterion must be verifiable by an automated test at the API boundary. "Nhanh", "thân thiện", "dễ dùng" are not criteria - convert to a number or move to NFR.
- For each feature, systematically cover: happy path, validation failure, permission denied, not found / other tenant, empty state, concurrency or duplicate submission when relevant, and what is audited.
- Do not invent business rules. When the input does not say, write the criterion with your best default AND add the question to open-questions.

### 2b. `docs/acceptance/inv.md` - business invariants (only when the system computes money, accounting, stock or aggregates)
Mã `INV`, criteria `AC-INV-NN`, same format. Properties that must hold for ALL data, not one example - e.g. debit = credit per (company, period); group report = sum of company reports; importing the same file twice changes nothing; a new version replaces only its own period range; every reported number drills down to rows summing to it; a user without access to company A sees nothing of A (API, export, drill-down). They are tested on a **golden dataset** (`backend/src/test/resources/golden/`: synthetic files from a fixed-seed generator + `expected.yaml` computed independently of production code - never real client data). Add the dataset itself as a question in open-questions if the client must supply sample formats.

### 3. `docs/open-questions.md`
Table: `| # | Câu hỏi | Vì sao cần chốt | Mặc định nếu khách không trả lời | Ảnh hưởng báo giá (Có/Không) |`. Order by impact on scope/price. These are what the user will send to the client. Carry over unanswered questions from `docs/scope.md`.

### 4. NFR section of the BRD
Fill from `${CLAUDE_PLUGIN_ROOT}/skills/spec/nfr-defaults.md`; only deviate when the input says so. If the system handles any personal data, classify it per `${CLAUDE_PLUGIN_ROOT}/skills/vn-data-protection/SKILL.md` (basic vs sensitive) - sensitive data changes the design and the price.

### Finish Step B
- `git add docs && git commit -m "spec: <summary>"`
- Set state: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dk-state.sh" set spec draft`.
- Reply in Vietnamese, max 10 lines: number of features, number of ACs (bắt buộc / tùy chọn), top 3 open questions, and: "Duyệt bằng `/dk:approve spec` khi đã chốt với khách."
