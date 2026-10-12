---
name: plan
description: Build or refresh the project schedule from the estimate — Gantt chart (docs/plan/gantt.html, Mermaid docs/plan/gantt.md) and the progress checklist docs/plan/tien-do.md that humans tick.
argument-hint: "[cập nhật | rebaseline | bắt đầu YYYY-MM-DD | N kỹ sư | gồm tùy chọn]"
disable-model-invocation: true
allowed-tools: Read, Edit, Bash
---

## Inputs
!`test -f docs/estimate/items.json && python3 -c "import json;d=json.load(open('docs/estimate/items.json'));p=d.get('params',{});it=d.get('items',[]);print(f\"items.json: {len(it)} hạng mục · id: {sum(1 for i in it if i.get('id'))}/{len(it)} · deps: {sum(1 for i in it if i.get('deps'))} · ac: {sum(1 for i in it if i.get('ac'))} · start_date={p.get('start_date')} · engineers={p.get('engineers')} · team={p.get('team')} · holidays={'có' if p.get('holidays') else 'mặc định'}\")" || echo "MISSING docs/estimate/items.json — run /dk:estimate first"`
!`test -f docs/plan/tien-do.md && python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gen-plan.py" --summary || echo "chưa có docs/plan/tien-do.md (lần đầu)"`

User request: $ARGUMENTS

## Task
1. If items.json is missing, stop and say so.
2. **First run, or items lack `id`/`deps`/`ac`** (see Inputs): edit `docs/estimate/items.json` only to add scheduling fields — never change `points`, `name`, `optional` or prices:
   - `id`: the feature Mã from `docs/scope.md` (e.g. `CTY`), stable forever — progress is matched by id.
   - `deps`: ids that must finish first (platform item first; reports after their data sources; "Kiểm thử nghiệm thu & sửa lỗi" and "Triển khai…" get `["*"]` = after everything listed before them). Keep chains short — over-constraining hides parallel work.
   - `ac`: AC prefixes of the feature, e.g. `["AC-CTY"]`.
   - `risk`: `HIGH` for money/accounting, permissions/tenancy, imports, PII, external systems; `LOW` for plain CRUD/UI; else `MEDIUM`.
   - `crew`: 2 only for items ≥ 10 points that can really be split.
   - `params.start_date` (ask the user if not given in the request; default next Monday), `params.team` (names of the 3 engineers if the user gave them), `params.holidays` (official VN holidays for the project years if known — Tết, Giỗ Tổ, make-up days; otherwise leave unset and mention the default).
3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gen-plan.py"` plus flags from the request: `--start YYYY-MM-DD`, `--engineers N`, `--include-optional`, `--rebaseline` (only when the user explicitly says rebaseline / lập lại kế hoạch gốc — it overwrites the baseline dates "KH").
4. Never edit `docs/plan/tien-do.md` by hand-written content: humans tick it (or use the "Tải tien-do.md" button in `gantt.html`); the script merges it. If the user tells you progress in chat ("CTY xong", "IMP 50%, Nam làm"), apply it with Edit to that item's line only (`[x]`, `tiến độ: N%`, `người:`, `bắt đầu:`, `xong:` in YYYY-MM-DD; remove "(theo AC)" when setting a % by hand), then run step 3 again.
5. Reply in Vietnamese, max 8 lines, copying numbers from the script output (never compute dates yourself): planned vs forecast acceptance date and slip, % done, late items (max 5), files written. Mention that `docs/plan/gantt.html` opens offline in any browser and `docs/plan/gantt.md` renders on GitHub. Suggest committing `docs/plan/` and `docs/estimate/items.json` together.
