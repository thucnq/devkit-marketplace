---
name: spec
description: Turn raw client input (chat logs, call notes, meeting notes) into a Vietnamese BRD, testable acceptance criteria, and a list of open questions for the client.
argument-hint: <path to notes file, or paste notes after the command>
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Bash
---

## Current state
!`cat .dk/state.md 2>/dev/null || echo "no .dk/state.md — run /dk:new-project first or create it"`

## Existing spec files
!`ls docs/brd.md docs/acceptance/ docs/open-questions.md 2>/dev/null || true`

## Input
$ARGUMENTS

## Task
Client input is always thin: a few headline features. Your value is the gap analysis a senior BA would do. Produce, all in Vietnamese:

### 1. `docs/brd.md` — follow `${CLAUDE_PLUGIN_ROOT}/skills/spec/brd-template.md` exactly
If the file exists, merge: keep approved sections, mark changes with `(cập nhật <date>)`.

### 2. `docs/acceptance/<feature-slug>.md` — one file per feature
Format each criterion as:
```
### AC-<FEAT>-<NN>: <tên ngắn>
- **Cho** <bối cảnh / dữ liệu sẵn có>
- **Khi** <hành động>
- **Thì** <kết quả quan sát được: HTTP status, dữ liệu, thông báo, bản ghi audit>
- Ưu tiên: Bắt buộc | Tùy chọn
```
FEAT is an UPPERCASE short code (ORDER, AUTH, REPORT). Rules:
- Every criterion must be verifiable by an automated test at the API boundary. "Nhanh", "thân thiện", "dễ dùng" are not criteria — convert to a number or move to NFR.
- For each feature, systematically cover: happy path, validation failure, permission denied, not found / other tenant, empty state, concurrency or duplicate submission when relevant, and what is audited.
- Do not invent business rules. When the input does not say, write the criterion with your best default AND add the question to open-questions.

### 3. `docs/open-questions.md`
Table: `| # | Câu hỏi | Vì sao cần chốt | Mặc định nếu khách không trả lời | Ảnh hưởng báo giá (Có/Không) |`. Order by impact on scope/price. These are what the user will send to the client.

### 4. NFR section of the BRD
Fill from `${CLAUDE_PLUGIN_ROOT}/skills/spec/nfr-defaults.md`; only deviate when the input says so. If the system handles any personal data, classify it per `${CLAUDE_PLUGIN_ROOT}/skills/vn-data-protection/SKILL.md` (basic vs sensitive) — sensitive data changes the design and the price.

### Finish
- `git add docs && git commit -m "spec: <summary>"`
- Set `spec: draft` in `.dk/state.md`.
- Reply in Vietnamese, max 10 lines: number of features, number of ACs (bắt buộc / tùy chọn), top 3 open questions, and: "Duyệt bằng `/dk:approve spec` khi đã chốt với khách."
