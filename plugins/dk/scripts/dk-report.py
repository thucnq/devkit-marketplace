#!/usr/bin/env python3
"""Turn .dk/log/*.jsonl into a retrospective report (Markdown) + metrics.json.

Usage: dk-report.py [out_dir]   (default .dk/retro)
Everything here is counted from the log; nothing is estimated by a model.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(".dk/log")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".dk/retro")


def load():
    events = []
    for f in sorted(LOG_DIR.glob("*.jsonl")):
        author = f.stem
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            e["author"] = author
            events.append(e)
    events.sort(key=lambda e: e.get("ts", ""))
    return events


def ts(e):
    try:
        return datetime.fromisoformat(e["ts"])
    except Exception:
        return None


def add_usage(acc, usage):
    for model, u in (usage or {}).items():
        a = acc.setdefault(model, Counter())
        a.update({k: v for k, v in u.items() if isinstance(v, int)})


def tok(u):
    return u.get("in", 0) + u.get("cache_read", 0) + u.get("cache_write", 0) + u.get("out", 0)


def fmt(n):
    return f"{n:,}".replace(",", ".")


def main():
    ev = load()
    if not ev:
        print("dk-report: chưa có log trong .dk/log/ - log được ghi tự động khi dùng plugin trong dự án.")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    first, last = ts(ev[0]), ts(ev[-1])
    authors = sorted({e["author"] for e in ev})

    usage_total, usage_by_cmd = {}, defaultdict(dict)
    cmds = Counter()
    prompts_by_cmd = Counter()
    tools = Counter()
    tool_fail = Counter()
    fail_samples = defaultdict(list)
    blocked = Counter()
    checks = defaultdict(Counter)
    check_fail_names = Counter()
    skipped = Counter()
    reviewer = Counter()
    reviewer_blockers = []
    gates = []
    gate_blocked = Counter()
    notes = []
    excuses = Counter()
    context_high = 0
    edited = Counter()
    feature_span = {}
    test_runs = Counter()
    first_check = {}
    sessions = set()

    for e in ev:
        t, cmd, feat = e.get("ev"), e.get("cmd") or "(ngoài lệnh dk)", e.get("feature")
        if e.get("sid"):
            sessions.add(e["sid"])
        if feat:
            a, b = feature_span.get(feat, (e["ts"], e["ts"]))
            feature_span[feat] = (min(a, e["ts"]), max(b, e["ts"]))
        if t == "command":
            cmds[e["cmd"]] += 1
        elif t == "prompt":
            prompts_by_cmd[cmd] += 1
        elif t == "usage":
            add_usage(usage_total, e.get("usage"))
            add_usage(usage_by_cmd[cmd], e.get("usage"))
        elif t == "subagent":
            add_usage(usage_total, e.get("usage"))
            add_usage(usage_by_cmd[cmd], e.get("usage"))
            if (e.get("agent") or "").endswith("reviewer") and e.get("verdict"):
                reviewer[e["verdict"]] += 1
                if e.get("blockers") is not None:
                    reviewer_blockers.append(e["blockers"])
        elif t == "tool":
            tools[e.get("tool")] += 1
            if e.get("tool") in ("Edit", "Write", "MultiEdit") and e.get("target"):
                edited[e["target"]] += 1
            if e.get("tool") == "Bash" and re.search(r"\b(mvnw?|npm|vitest)\b.*\btest\b", e.get("target") or ""):
                test_runs[feat or "-"] += 1
        elif t == "tool_fail":
            tool_fail[e.get("tool")] += 1
            if len(fail_samples[e.get("tool")]) < 3:
                fail_samples[e.get("tool")].append(e.get("error", "")[:140])
        elif t == "blocked":
            blocked[e.get("rule")] += 1
        elif t == "check":
            checks[e.get("mode")][e.get("result")] += 1
            for n in filter(None, (e.get("failed") or "").split(";")):
                check_fail_names[n.strip()] += 1
            for n in filter(None, (e.get("skipped") or "").split(";")):
                skipped[n.strip()] += 1
            key = (feat, e.get("mode"))
            first_check.setdefault(key, e.get("result"))
        elif t == "gate":
            gates.append((e["ts"][:10], e.get("gate"), e.get("rev"), e["author"]))
        elif t == "gate_blocked":
            gate_blocked[e.get("gate")] += 1
        elif t == "note":
            notes.append(e)
        elif t == "excuse":
            for k in e.get("keys") or []:
                excuses[k] += 1
        elif t == "context_high":
            context_high += 1

    total_tok = sum(tok(u) for u in usage_total.values())
    cache_read = sum(u.get("cache_read", 0) for u in usage_total.values())
    cache_ratio = cache_read / total_tok if total_tok else 0

    estimate = None
    est_file = Path("docs/estimate/items.json")
    if est_file.exists():
        try:
            items = json.loads(est_file.read_text(encoding="utf-8")).get("items", [])
            estimate = {"mandatory_points": sum(float(i["points"]) for i in items if not i.get("optional")),
                        "optional_points": sum(float(i["points"]) for i in items if i.get("optional"))}
        except Exception:
            pass

    days = (last - first).days + 1 if first and last else None
    metrics = {
        "period": {"from": ev[0]["ts"], "to": ev[-1]["ts"], "calendar_days": days},
        "authors": authors, "sessions": len(sessions), "events": len(ev),
        "commands": dict(cmds), "human_prompts_by_command": dict(prompts_by_cmd),
        "tokens": {"total": total_tok, "cache_read_ratio": round(cache_ratio, 3),
                   "by_model": {m: dict(u) for m, u in usage_total.items()},
                   "by_command": {c: sum(tok(u) for u in m.values()) for c, m in usage_by_cmd.items()}},
        "tools": dict(tools), "tool_failures": dict(tool_fail),
        "guard_blocks": dict(blocked), "gate_blocked": dict(gate_blocked), "gates": gates,
        "checks": {m: dict(c) for m, c in checks.items()}, "check_failures": dict(check_fail_names),
        "skipped_checks": dict(skipped),
        "first_check_result": {f"{k[0]}|{k[1]}": v for k, v in first_check.items()},
        "reviewer": dict(reviewer), "reviewer_blockers": reviewer_blockers,
        "test_runs_by_feature": dict(test_runs),
        "feature_span": {f: {"from": a, "to": b} for f, (a, b) in feature_span.items()},
        "most_edited": edited.most_common(15), "estimate": estimate,
        "excuse_signals": dict(excuses), "context_high_notices": context_high,
        "notes": [{"ts": n["ts"], "author": n["author"], "tags": n.get("tags"), "text": n.get("text")} for n in notes],
    }
    stamp = (last or datetime.now()).strftime("%Y%m%d")
    (OUT / f"{stamp}-metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    L = [f"# Báo cáo log dự án - {Path.cwd().name}", "",
         f"Từ {ev[0]['ts'][:10]} đến {ev[-1]['ts'][:10]} ({days} ngày) · {len(authors)} người ({', '.join(authors)}) · "
         f"{len(sessions)} phiên · {fmt(len(ev))} sự kiện", "",
         "## Token", "",
         f"Tổng {fmt(total_tok)} token · tỷ lệ đọc từ cache {cache_ratio:.0%} (càng cao càng rẻ)", "",
         "| Lệnh | Số lần gọi | Token | Prompt bổ sung của người |", "|---|---:|---:|---:|"]
    all_cmds = sorted(set(cmds) | set(usage_by_cmd) | set(prompts_by_cmd),
                      key=lambda c: -sum(tok(u) for u in usage_by_cmd.get(c, {}).values()))
    for c in all_cmds:
        if not (cmds.get(c) or prompts_by_cmd.get(c) or usage_by_cmd.get(c)):
            continue
        L.append(f"| {c} | {cmds.get(c, 0)} | {fmt(sum(tok(u) for u in usage_by_cmd.get(c, {}).values()))} | {prompts_by_cmd.get(c, 0)} |")
    L += ["", "| Model | Input | Cache đọc | Cache ghi | Output | Lượt gọi |", "|---|---:|---:|---:|---:|---:|"]
    for m, u in usage_total.items():
        L.append(f"| {m} | {fmt(u.get('in', 0))} | {fmt(u.get('cache_read', 0))} | {fmt(u.get('cache_write', 0))} | {fmt(u.get('out', 0))} | {u.get('calls', 0)} |")

    L += ["", "## Chất lượng", "",
          f"- Reviewer: {reviewer.get('APPROVE', 0)} APPROVE, {reviewer.get('CHANGES_REQUIRED', 0)} CHANGES_REQUIRED"
          + (f", trung bình {sum(reviewer_blockers) / len(reviewer_blockers):.1f} blocker/lần" if reviewer_blockers else ""),
          "- Kiểm tra tất định: " + (", ".join(f"{m} {c.get('PASS', 0)} đạt / {c.get('FAIL', 0)} trượt" for m, c in checks.items()) or "chưa chạy")]
    if check_fail_names:
        L.append("- Bước hay trượt nhất: " + ", ".join(f"{n} ({c})" for n, c in check_fail_names.most_common(6)))
    if skipped:
        L.append("- Bị bỏ qua vì thiếu công cụ: " + ", ".join(f"{n} ({c})" for n, c in skipped.most_common()))
    if test_runs:
        L.append("- Số lần chạy test theo tính năng: " + ", ".join(f"{f} {c}" for f, c in test_runs.most_common()))

    L += ["", "## Ma sát", ""]
    L.append("- Hook chặn: " + (", ".join(f"{r} ({c})" for r, c in blocked.most_common()) or "không có"))
    L.append("- Cổng chưa duyệt mà vẫn gọi lệnh: " + (", ".join(f"{g} ({c})" for g, c in gate_blocked.items()) or "không có"))
    L.append("- Tool lỗi: " + (", ".join(f"{t} ({c})" for t, c in tool_fail.most_common()) or "không có"))
    L.append("- Câu trả lời có dấu hiệu bỏ dở (lỗi có sẵn, flaky, bỏ qua test, để sau…): "
             + (", ".join(f"{k} ({c})" for k, c in excuses.most_common()) or "không có"))
    L.append(f"- Nhắc /compact vì ngữ cảnh lớn: {context_high} lần")
    for t, samples in fail_samples.items():
        for s in samples:
            L.append(f"  - {t}: `{s}`")
    if gates:
        L += ["", "## Cổng duyệt", "", "| Ngày | Cổng | Commit | Người duyệt |", "|---|---|---|---|"]
        L += [f"| {d} | {g} | {r} | {a} |" for d, g, r, a in gates]
        churn = Counter(g for _, g, _, _ in gates)
        if any(c > 1 for c in churn.values()):
            L.append("")
            L.append("Duyệt lại nhiều lần (dấu hiệu phạm vi thay đổi): " + ", ".join(f"{g} ×{c}" for g, c in churn.items() if c > 1))

    L += ["", "## Tiến độ", ""]
    if estimate:
        L.append(f"- Ước lượng: {estimate['mandatory_points']:g} điểm bắt buộc + {estimate['optional_points']:g} tùy chọn; thời gian thực tế trong log: {days} ngày lịch")
    for f, (a, b) in sorted(feature_span.items(), key=lambda x: x[1][0]):
        d = (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days + 1
        L.append(f"- {f}: {a[:10]} → {b[:10]} ({d} ngày)")
    if edited:
        L += ["", "File bị sửa nhiều nhất:", ""]
        L += [f"- `{p}` ×{c}" for p, c in edited.most_common(10)]

    L += ["", "## Ghi chú của nhóm", ""]
    if notes:
        by_tag = defaultdict(list)
        for n in notes:
            for tg in n.get("tags") or ["general"]:
                by_tag[tg].append(n)
        for tg, ns in sorted(by_tag.items()):
            L.append(f"### #{tg}")
            L += [f"- {n['ts'][:10]} ({n['author']}): {n.get('text')}" for n in ns]
            L.append("")
    else:
        L.append("Chưa có ghi chú. Dùng `/dk:note #tag nội dung` ngay khi gặp vấn đề.")

    report = OUT / f"{stamp}-report.md"
    report.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"dk-report: {report} và {OUT / (stamp + '-metrics.json')}")
    print(f"  {len(ev)} sự kiện · {fmt(total_tok)} token · reviewer {dict(reviewer) or '-'} · hook chặn {sum(blocked.values())} · {len(notes)} ghi chú")
    return 0


if __name__ == "__main__":
    sys.exit(main())
