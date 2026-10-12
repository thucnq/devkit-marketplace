#!/usr/bin/env python3
"""Schedule + progress from the estimate. Deterministic, no LLM, standard library only.

Usage:
  gen-plan.py [docs/estimate/items.json] [--start YYYY-MM-DD] [--engineers N] [--include-optional]
              [--rebaseline] [--out docs/plan]
  gen-plan.py --summary            one status line (session-start hook)

Reads   docs/estimate/items.json         (items, params; see skills/estimate/items.schema.md)
        docs/plan/tien-do.md             (if present: what humans ticked/typed — the source of truth for progress)
        docs/acceptance/*.md + tests     (AC lists per item, "has test" flag)
Writes  docs/plan/tien-do.md             checklist: items + their ACs, baseline dates, editable progress fields
        docs/plan/gantt.html             self-contained Gantt + checklist (no CDN, works offline)
        docs/plan/gantt.md               Mermaid gantt (renders on GitHub)
        docs/plan/plan.json              computed schedule (for other tools)

Scheduling: effort (days) = points × (1 + overhead_pct); one engineer per item unless "crew": n.
List scheduling in item order over `engineers` lanes, honouring "deps" ("*" = every earlier item).
Baseline ("KH") is frozen in tien-do.md on first run; `--rebaseline` recomputes it.
Forecast ("DB") replans remaining work from today using actual starts, % done and finish dates.
"""
import argparse
import datetime as dt
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TODAY = dt.date.today()

# Vietnamese public holidays. Fixed solar dates every year; lunar ones (Tết, Giỗ Tổ) and official
# make-up days change yearly — defaults below are the announced/expected ones: CHECK each year and put
# the official list into params.holidays (it replaces the lunar defaults).
FIXED_HOLIDAYS = ["01-01", "04-30", "05-01", "09-02"]
LUNAR_DEFAULTS = ["2026-02-14..2026-02-22", "2026-04-27", "2026-09-01",
                  "2027-02-04..2027-02-10"]  # 2027: dự kiến, chưa có thông báo chính thức

STATUS_VI = {"done": "Xong", "doing": "Đang làm", "todo": "Chưa bắt đầu", "late": "Trễ"}


def load_trace():
    """Reuse ac-trace.py (project copy wins) for AC lists and test references."""
    for p in (Path("tools/ac-trace.py"), HERE / "ac-trace.py"):
        if p.exists():
            spec = importlib.util.spec_from_file_location("ac_trace", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


# ---------------------------------------------------------------- calendar
def parse_date(s):
    return dt.date.fromisoformat(s.strip()) if s and s.strip() else None


def holiday_set(params, years):
    days = set()
    for y in years:
        for md in FIXED_HOLIDAYS:
            days.add(dt.date.fromisoformat(f"{y}-{md}"))
    for spec in params.get("holidays") or LUNAR_DEFAULTS:
        a, _, b = spec.partition("..")
        d0, d1 = parse_date(a), parse_date(b or a)
        while d0 <= d1:
            days.add(d0)
            d0 += dt.timedelta(days=1)
    return days


class Cal:
    def __init__(self, holidays):
        self.h = holidays

    def work(self, d):
        return d.weekday() < 5 and d not in self.h

    def next_work(self, d):
        while not self.work(d):
            d += dt.timedelta(days=1)
        return d

    def after(self, d):  # first working day strictly after d
        return self.next_work(d + dt.timedelta(days=1))

    def end(self, start, n):  # last day of n working days beginning at start (start is a working day)
        d, left = start, max(1, n) - 1
        while left:
            d = self.after(d)
            left -= 1
        return d

    def between(self, a, b):  # working days in [a, b]
        n, d = 0, a
        while d <= b:
            n += self.work(d)
            d += dt.timedelta(days=1)
        return n


# ---------------------------------------------------------------- progress file
ITEM_RE = re.compile(r"^- \[( |x|X)\] \*\*(\S+)\*\*\s*(.*)$")
AC_RE = re.compile(r"^\s+- \[( |x|X)\] (AC-[A-Z0-9]+-[A-Z0-9]+)\b")


def read_progress(path):
    prog = {}
    if not path.exists():
        return prog
    cur = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ITEM_RE.match(line)
        if m:
            fields = {}
            for part in m.group(3).split(" · ")[1:]:
                k, sep, v = part.partition(":")
                if sep:
                    fields[k.strip().lower()] = v.strip()
            kh = re.match(r"(\d{4}-\d{2}-\d{2})\s*→\s*(\d{4}-\d{2}-\d{2})", fields.get("kh", ""))
            pct = re.match(r"(\d+)", fields.get("tiến độ", ""))
            if "theo AC" in fields.get("tiến độ", ""):
                pct = None  # derived from the AC checkboxes; delete "(theo AC)" to type a % by hand
            cur = prog[m.group(2)] = {
                "checked": m.group(1) != " ",
                "pct": int(pct.group(1)) if pct else None,
                "owner": fields.get("người", ""),
                "start": fields.get("bắt đầu", ""),
                "finish": fields.get("xong", ""),
                "note": fields.get("ghi chú", ""),
                "kh": (kh.group(1), kh.group(2)) if kh else None,
                "acs": {},
            }
            continue
        m = AC_RE.match(line)
        if m and cur is not None:
            cur["acs"][m.group(2)] = m.group(1) != " "
    return prog


# ---------------------------------------------------------------- scheduling
def schedule(items, lanes, cal, start, mode, prog=None):
    """Return {id: (start, end, lane)}. mode='ideal' ignores progress; 'forecast' replans from today."""
    lane_free = {name: start for name in lanes}  # first working day each lane is free
    out, order = {}, [it["id"] for it in items]
    rank = {"done": 0, "doing": 1} if mode == "forecast" else {}
    pending = sorted(items, key=lambda it: rank.get(it["status"], 2))  # stable: work already started keeps its lane
    now = cal.next_work(max(TODAY, start))
    while pending:
        progressed = False
        for it in list(pending):
            deps = order[:order.index(it["id"])] if "*" in it["deps"] else it["deps"]
            if any(d not in out for d in deps if d in order):
                continue
            pending.remove(it)
            progressed = True
            dep_ready = max([cal.after(out[d][1]) for d in deps if d in out] or [start])
            p = (prog or {}).get(it["id"], {})
            dur = it["days"]
            fixed_start = None
            if mode == "forecast":
                if it["status"] == "done":
                    s = parse_date(p.get("start")) or (p.get("kh") and parse_date(p["kh"][0])) or dep_ready
                    e = parse_date(p.get("finish")) or min(TODAY, cal.end(s, dur))
                    out[it["id"]] = (s, max(s, e), it.get("lane") or "")
                    continue
                if it["status"] == "doing":
                    fixed_start = parse_date(p.get("start")) or now
                    dur = max(1, math.ceil(it["days"] * (1 - it["pct"] / 100)))
                dep_ready = max(dep_ready, now)
            lane_names = choose_lanes(lanes, lane_free, it, mode)
            s = cal.next_work(max([dep_ready] + [lane_free[n] for n in lane_names]))
            if fixed_start:  # already running: bar starts at the real start, remaining work from today
                e = cal.end(cal.next_work(max(now, dep_ready)), dur)
                s = min(fixed_start, e)
            else:
                e = cal.end(s, dur)
            for n in lane_names:
                lane_free[n] = cal.after(e)
            out[it["id"]] = (s, e, ", ".join(lane_names))
        if not progressed:  # dependency cycle or unknown id: schedule the rest ignoring deps
            for it in pending:
                it["deps"] = []
    return out


def choose_lanes(lanes, lane_free, it, mode):
    crew = min(max(1, int(it.get("crew", 1))), len(lanes))
    owner = it.get("owner_lane")
    ranked = sorted(lanes, key=lambda n: (lane_free[n], lanes.index(n)))
    if owner in lanes:
        ranked.remove(owner)
        ranked.insert(0, owner)
    return ranked[:crew]


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="?", default="docs/estimate/items.json")
    ap.add_argument("--start")
    ap.add_argument("--engineers", type=int)
    ap.add_argument("--include-optional", action="store_true")
    ap.add_argument("--rebaseline", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--out", default="docs/plan")
    a = ap.parse_args()

    src = Path(a.items)
    if not src.exists():
        print(f"gen-plan: thiếu {src} — chạy /dk:estimate trước")
        return 0 if a.summary else 1
    data = json.loads(src.read_text(encoding="utf-8"))
    p = data.get("params", {})
    out_dir = Path(a.out)
    prog_path = out_dir / "tien-do.md"
    prog = read_progress(prog_path)

    overhead = float(p.get("overhead_pct", 0.3))
    team = p.get("team") or []
    n_eng = a.engineers or int(p.get("engineers", max(1, len(team)) or 3))
    lanes = [str(t) for t in team][:n_eng] + [f"Kỹ sư {i + 1}" for i in range(len(team), n_eng)]
    stored_start = re.search(r"Bắt đầu dự án: (\d{4}-\d{2}-\d{2})", prog_path.read_text(encoding="utf-8")) if prog_path.exists() else None
    stored = stored_start.group(1) if stored_start else None
    # the start date is frozen with the baseline; params.start_date only applies to a new plan or --rebaseline
    start = parse_date(a.start or (p.get("start_date") if a.rebaseline else stored) or p.get("start_date") or stored or "")
    if not start:
        start = TODAY + dt.timedelta(days=(7 - TODAY.weekday()) % 7 or 7)  # next Monday
    years = range(start.year, start.year + 3)
    cal = Cal(holiday_set(p, years))
    start = cal.next_work(start)

    trace = load_trace()
    all_acs = trace.load_acs() if trace and Path("docs/acceptance").is_dir() else {}
    refs = trace.load_refs() if all_acs else {}

    include_opt = a.include_optional or bool(p.get("plan_optional"))
    items, seen = [], set()
    for i, raw in enumerate(data.get("items", []), 1):
        if raw.get("optional") and not include_opt:
            continue
        iid = str(raw.get("id") or f"H{i:02d}")
        if iid in seen:
            iid = f"{iid}-{i}"
        seen.add(iid)
        pts = float(raw.get("points", 0))
        crew = max(1, int(raw.get("crew", 1)))
        days = max(1, math.ceil(pts * (1 + overhead) / crew))
        prefixes = raw.get("ac") or sorted(set(re.findall(r"AC-[A-Z0-9]+", raw.get("desc", ""))))
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        acs = [ac for ac in all_acs if any(ac == x or ac.startswith(x.rstrip("-") + "-") for x in prefixes)]
        pr = prog.get(iid, {})
        owner = pr.get("owner") or raw.get("owner") or ""
        items.append({
            "id": iid, "module": raw.get("module", "Khác"), "name": raw.get("name", iid),
            "points": pts, "days": days, "crew": crew, "risk": (raw.get("risk") or "MEDIUM").upper(),
            "deps": [str(d) for d in raw.get("deps", [])], "optional": bool(raw.get("optional")),
            "owner": owner, "owner_lane": next((ln for ln in lanes if ln.lower() == owner.lower()), None),
            "acs": [{"id": ac, "title": all_acs[ac]["title"], "optional": all_acs[ac]["optional"],
                     "tested": ac in refs, "done": pr.get("acs", {}).get(ac, False)} for ac in acs],
            "start_actual": pr.get("start", ""), "finish_actual": pr.get("finish", ""), "note": pr.get("note", ""),
            "checked": pr.get("checked", False), "pct_manual": pr.get("pct"), "pct_auto": False,
        })

    # status / percent
    for it in items:
        if it["checked"]:
            it["pct"] = 100
        elif it["pct_manual"] is not None:
            it["pct"] = max(0, min(99, it["pct_manual"]))
        elif it["acs"]:
            it["pct"] = min(99, round(100 * sum(x["done"] for x in it["acs"]) / len(it["acs"])))
            it["pct_auto"] = True
        else:
            it["pct"] = 0
        it["status"] = "done" if it["pct"] == 100 else ("doing" if it["pct"] > 0 or it["start_actual"] else "todo")

    ideal = schedule([dict(it) for it in items], lanes, cal, start, "ideal")
    fc = schedule([dict(it) for it in items], lanes, cal, start, "forecast", prog)
    for it in items:
        old = prog.get(it["id"], {}).get("kh")
        if old and not a.rebaseline:
            it["kh"] = (parse_date(old[0]), parse_date(old[1]))
        else:
            it["kh"] = ideal[it["id"]][:2]
        it["fc"] = fc[it["id"]][:2]
        it["lane"] = it["owner"] or ideal[it["id"]][2]
        if it["status"] != "done" and (it["fc"][1] > it["kh"][1] or (it["status"] == "todo" and TODAY > it["kh"][0])):
            it["status"] = "late"
        it["slip"] = cal.between(cal.after(it["kh"][1]), it["fc"][1]) if it["fc"][1] > it["kh"][1] else 0

    if not items:
        print("gen-plan: items.json không có hạng mục nào")
        return 1
    uat_days = int(p.get("uat_weeks", 2)) * 5
    kh_end = max(it["kh"][1] for it in items)
    fc_end = max(it["fc"][1] for it in items)
    kh_uat = (cal.after(kh_end), cal.end(cal.after(kh_end), uat_days))
    fc_uat = (cal.after(fc_end), cal.end(cal.after(fc_end), uat_days))
    tot_pts = sum(it["points"] for it in items) or 1
    done_pct = sum(it["points"] * it["pct"] for it in items) / tot_pts
    counts = {k: sum(1 for it in items if it["status"] == k) for k in STATUS_VI}
    slip = cal.between(cal.after(kh_uat[1]), fc_uat[1]) if fc_uat[1] > kh_uat[1] else 0
    summary = (f"tiến độ: {done_pct:.0f}% theo điểm · xong {counts['done']} · đang làm {counts['doing']} · "
               f"trễ {counts['late']} · chưa bắt đầu {counts['todo']} · nghiệm thu KH {kh_uat[1]} / dự báo {fc_uat[1]}"
               + (f" (trễ {slip} ngày làm việc)" if slip else ""))
    if a.summary:
        print(summary)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": data.get("title", "Kế hoạch dự án").replace("BÁO GIÁ", "KẾ HOẠCH"),
        "start": start, "engineers": n_eng, "lanes": lanes, "overhead": overhead,
        "kh_uat": kh_uat, "fc_uat": fc_uat, "today": TODAY, "uat_weeks": int(p.get("uat_weeks", 2)),
        "holidays": sorted(d for d in cal.h if start - dt.timedelta(days=7) <= d <= fc_uat[1] + dt.timedelta(days=60)),
        "pct": round(done_pct, 1), "counts": counts, "slip": slip, "src": str(src),
    }
    md_lines, line_of = render_md(items, meta)
    (out_dir / "tien-do.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    (out_dir / "gantt.md").write_text(render_mermaid(items, meta), encoding="utf-8")
    payload = to_json(items, meta, md_lines, line_of)
    (out_dir / "plan.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tpl = (HERE / "gantt-template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    html = html.replace("__TITLE__", esc(meta["title"]))
    (out_dir / "gantt.html").write_text(html, encoding="utf-8")

    print(f"gen-plan: {len(items)} hạng mục{' (gồm tùy chọn)' if include_opt else ' bắt buộc'}, "
          f"{n_eng} kỹ sư ({', '.join(lanes)}), bắt đầu {start}")
    print(f"  kế hoạch: code xong {kh_end}, UAT {meta['uat_weeks']} tuần → nghiệm thu {kh_uat[1]}"
          f" · dự báo: nghiệm thu {fc_uat[1]}" + (f" (trễ {slip} ngày làm việc)" if slip else " (đúng hạn)"))
    wdm = float(p.get("working_days_per_month", 22))
    ideal_m = sum(it["points"] for it in items) * (1 + overhead) / n_eng / wdm
    sched_m = cal.between(start, kh_end) / wdm
    print(f"  báo giá giả định ~{ideal_m:.1f} tháng (chia đều {n_eng} kỹ sư) · lịch theo phụ thuộc {sched_m:.1f} tháng code"
          + (" — phụ thuộc làm dài lịch, xem lại deps hoặc báo khách mốc thực tế" if sched_m > ideal_m * 1.25 else ""))
    print(f"  {summary}")
    lates = [it for it in items if it["status"] == "late"][:5]
    for it in lates:
        print(f"  TRỄ {it['id']} {it['name']}: KH xong {it['kh'][1]}, dự báo {it['fc'][1]}")
    unmapped = sum(1 for it in items if not it["acs"] and it["module"] != "Nền tảng")
    if all_acs and unmapped:
        print(f"  {unmapped} hạng mục chưa gắn AC (thêm \"ac\": [\"AC-<MÃ>\"] trong items.json)")
    if not p.get("holidays"):
        print("  ngày nghỉ âm lịch dùng mặc định trong gen-plan.py — kiểm tra lại và đặt params.holidays")
    print(f"  → {out_dir}/tien-do.md · {out_dir}/gantt.html · {out_dir}/gantt.md")
    return 0


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_md(items, m):
    L = [f"# Tiến độ — {m['title']}", "",
         "> Sinh bởi `/dk:plan` (gen-plan.py) từ `" + m["src"] + "`. **Người sửa trực tiếp file này**: dấu `[x]` (hạng mục hoặc AC), "
         "`tiến độ: N%`, `người`, `bắt đầu`, `xong` (YYYY-MM-DD), `ghi chú` — giữ nguyên dấu ` · ` giữa các trường. "
         "Chạy lại `/dk:plan` để tính dự báo và vẽ lại `gantt.html`. `KH` là kế hoạch gốc, chỉ đổi bằng `/dk:plan rebaseline`.",
         f"> Bắt đầu dự án: {m['start']} · Kỹ sư: {m['engineers']} ({', '.join(m['lanes'])}) · "
         f"Nghiệm thu KH: {m['kh_uat'][1]} · Dự báo: {m['fc_uat'][1]} · Cập nhật: {m['today']}", ""]
    line_of = {}
    module = None
    for it in items:
        if it["module"] != module:
            module = it["module"]
            L += ["", f"## {module}"]
        line_of[it["id"]] = len(L)
        L.append(f"- [{'x' if it['pct'] == 100 else ' '}] **{it['id']}** {it['name']} · {it['points']:g}đ · rủi ro: {it['risk']}"
                 f" · KH: {it['kh'][0]} → {it['kh'][1]} · tiến độ: {it['pct']}%{' (theo AC)' if it['pct_auto'] else ''}"
                 f" · người: {it['owner']}"
                 f" · bắt đầu: {it['start_actual']} · xong: {it['finish_actual']} · ghi chú: {it['note']}")
        for ac in it["acs"]:
            line_of[f"{it['id']}/{ac['id']}"] = len(L)
            L.append(f"  - [{'x' if ac['done'] else ' '}] {ac['id']} {ac['title']}"
                     + (" _(tùy chọn)_" if ac["optional"] else ""))
    return L, line_of


def render_mermaid(items, m):
    def clean(s):
        return re.sub(r"[:#;,]", " ", s)
    ex = ", ".join(["weekends"] + [d.isoformat() for d in m["holidays"]])
    out = [f"# Gantt — {m['title']}", "",
           f"Tiến độ {m['pct']:.0f}% · nghiệm thu KH {m['kh_uat'][1]} · dự báo {m['fc_uat'][1]}. Bản tương tác: `gantt.html`.", "",
           "```mermaid", "gantt", f"    title {clean(m['title'])}", "    dateFormat YYYY-MM-DD", f"    excludes {ex}",
           "    todayMarker stroke-width:2px,stroke:#d33"]
    module = None
    for it in items:
        if it["module"] != module:
            module = it["module"]
            out.append(f"    section {clean(module)}")
        tag = {"done": "done, ", "doing": "active, ", "late": "crit, "}.get(it["status"], "")
        n = sum(1 for k in range((it["fc"][1] - it["fc"][0]).days + 1)
                if (d := it["fc"][0] + dt.timedelta(days=k)).weekday() < 5 and d not in m["holidays"]) or 1
        out.append(f"    {clean(it['id'] + ' ' + it['name'])} ({it['pct']}%) :{tag}{it['id'].replace('-', '_')}, {it['fc'][0]}, {n}d")
    out += ["    section Bàn giao", f"    UAT {m['uat_weeks']} tuần :uat, {m['fc_uat'][0]}, {m['uat_weeks'] * 5}d",
            f"    Nghiệm thu :milestone, {m['fc_uat'][1]}, 0d", "```", ""]
    return "\n".join(out)


def to_json(items, m, md_lines, line_of):
    iso = lambda d: d.isoformat()  # noqa: E731
    return {
        "meta": {"title": m["title"], "start": iso(m["start"]), "today": iso(m["today"]), "lanes": m["lanes"],
                 "khUat": [iso(d) for d in m["kh_uat"]], "fcUat": [iso(d) for d in m["fc_uat"]],
                 "holidays": [iso(d) for d in m["holidays"]], "pct": m["pct"], "counts": m["counts"],
                 "slip": m["slip"], "uatWeeks": m["uat_weeks"], "statusVi": STATUS_VI},
        "items": [{"id": it["id"], "module": it["module"], "name": it["name"], "points": it["points"],
                   "days": it["days"], "risk": it["risk"], "deps": it["deps"], "owner": it["owner"], "lane": it["lane"],
                   "pct": it["pct"], "pctAuto": it["pct_auto"], "status": it["status"], "slip": it["slip"], "note": it["note"],
                   "startActual": it["start_actual"], "finishActual": it["finish_actual"],
                   "kh": [iso(d) for d in it["kh"]], "fc": [iso(d) for d in it["fc"]], "line": line_of[it["id"]],
                   "acs": [dict(ac, line=line_of[f"{it['id']}/{ac['id']}"]) for ac in it["acs"]]} for it in items],
        "md": md_lines,
    }


if __name__ == "__main__":
    sys.exit(main())
