#!/usr/bin/env python3
"""Signs of unfinished work in a dk project, each with its evidence (zero tokens: git and .dk/ only, no network).

Usage: dk-unfinished.py [--max N] [--days D]
Prints nothing when there is no sign. session-start.sh runs it so that, when the human says "tiếp tục việc đang dở",
the agent names the work and quotes the evidence (commit, check report line, log time) instead of guessing.

Signs:
  - uncommitted changes outside .dk/
  - a branch with commits not in the base branch: not pushed, pushed without being merged, or merged as a PR while
    later commits stayed on the branch (patch-identical cherry-picks count as merged)
  - the last dk-check FAILED
  - RED evidence recorded without GREEN
  - spec/contract files changed after the gate was approved
  - /dk:review started on a branch that never got `review-<branch>: approved`
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SPEC_PATHS = ["docs/acceptance", "docs/brd.md"]
CONTRACT_PATHS = ["docs/api/openapi.yaml"]
MERGE_PR = re.compile(r"Merge pull request #(\d+) from [^/\s]+/(\S+)")


def git(root, *args):
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5)
        return out.stdout.rstrip() if out.returncode == 0 else ""
    except Exception:
        return ""


def lines(text):
    return [s for s in text.splitlines() if s.strip()]


def base_ref(root):
    head = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    for ref in (head, "origin/main", "origin/master", "main", "master"):
        if ref and git(root, "rev-parse", "--verify", "-q", ref):
            return ref
    return ""


def state(root):
    f = root / ".dk/state.md"
    out = {}
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    return out


def short(commits, n=3, width=70):
    shown = "; ".join(c if len(c) <= width else c[: width - 1] + "…" for c in commits[:n])
    return shown + (f" (+{len(commits) - n} commit)" if len(commits) > n else "")


def uncommitted(root):
    files = [s for s in lines(git(root, "status", "--porcelain")) if not s[3:].startswith(".dk/")]
    if files:
        more = f" (+{len(files) - 3} file)" if len(files) > 3 else ""
        yield "thay đổi chưa commit", "git status: " + ", ".join(s.strip() for s in files[:3]) + more


def branches(root, base, days):
    merges = {}
    for row in lines(git(root, "log", base, "--merges", "--format=%h%x09%s", "-n", "500")):
        sha, _, subject = row.partition("\t")
        m = MERGE_PR.search(subject)
        if m:
            merges.setdefault(m.group(2), (m.group(1), sha))
    since = datetime.now(timezone.utc).timestamp() - days * 86400
    fmt = "%(refname:short)%09%(committerdate:unix)%09%(committerdate:format:%Y-%m-%d %H:%M)%09%(upstream:short)"
    for row in lines(git(root, "for-each-ref", "--no-merged", base, f"--format={fmt}", "refs/heads")):
        name, stamp, when, upstream = (row.split("\t") + ["", "", "", ""])[:4]
        if not stamp.isdigit() or int(stamp) < since:
            continue  # old branches are history, not work in progress
        # `git cherry` drops commits whose patch is already in base (cherry-picked or rebased elsewhere)
        left = [s[2:] for s in lines(git(root, "cherry", base, name)) if s.startswith("+ ")]
        if not left:
            continue
        log = dict(r.split(" ", 1) for r in lines(git(root, "log", "--format=%H %h %s", f"{base}..{name}")))
        commits = [log.get(sha, sha[:7]) for sha in left]
        if name in merges:
            pr, sha = merges[name]
            sign = f"nhánh {name}: PR #{pr} đã merge ({sha}) nhưng còn {len(commits)} commit chưa vào {base}"
        elif not upstream:
            sign = f"nhánh {name}: {len(commits)} commit chưa push"
        elif git(root, "rev-list", "--count", f"{upstream}..{name}") not in ("", "0"):
            ahead = git(root, "rev-list", "--count", f"{upstream}..{name}")
            sign = f"nhánh {name}: {ahead} commit chưa push lên {upstream}"
        else:
            sign = f"nhánh {name}: {len(commits)} commit đã push nhưng chưa vào {base} (kiểm PR)"
        yield sign, f"commit cuối {when}: {short(commits)}"


def last_check(root):
    f = root / ".dk/check-report.md"
    if not f.exists():
        return
    text = f.read_text(encoding="utf-8", errors="ignore")
    head = text.splitlines()[0] if text else ""
    if not head.startswith("FAIL"):
        return
    failed = re.findall(r"^\|\s*([^|]+?)\s*\|\s*\*\*FAIL\*\*", text, re.M)
    parts = [s.strip() for s in head.split("·")]
    sha = parts[3] if len(parts) > 3 else ""
    moved = sha and git(root, "rev-parse", "--short", "HEAD") != sha
    yield (
        "lần dk-check gần nhất FAIL" + (" (HEAD đã đổi từ đó, cần chạy lại)" if moved else ""),
        f".dk/check-report.md: \"{head}\" - đỏ: {', '.join(failed) or 'xem báo cáo'}",
    )


def evidence(root):
    for f in sorted((root / ".dk/evidence").glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        red = data.get("red") if isinstance(data, dict) else None
        if isinstance(red, dict) and not data.get("green"):
            yield (
                f"tính năng {f.stem}: có RED, chưa có GREEN",
                f"{f.relative_to(root)}: red lúc {red.get('ts', '?')} tại {red.get('commit', '?')}",
            )


def gates(root, st):
    for gate, paths in (("spec", SPEC_PATHS), ("contract", CONTRACT_PATHS)):
        m = re.match(r"approved \S+ by .+ at (\S+)$", st.get(gate, ""))
        if not m or not git(root, "rev-parse", "--verify", "-q", m.group(1)):
            continue
        rev = m.group(1)
        if subprocess.run(["git", "merge-base", "--is-ancestor", rev, "HEAD"], cwd=root, capture_output=True).returncode:
            continue  # approved on another line of history
        changed = lines(git(root, "log", "--format=%h %s", f"{rev}..HEAD", "--", *paths))
        if changed:
            yield f"{' và '.join(paths)} đổi sau khi duyệt cổng {gate} ({rev})", short(changed)


def reviews(root, st, base):
    started = {}
    for f in sorted((root / ".dk/log").glob("*.jsonl")):
        for raw in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if '"dk:review"' not in raw:
                continue
            try:
                e = json.loads(raw)
            except Exception:
                continue
            b = e.get("branch")
            if e.get("cmd") == "dk:review" and b and b not in started:
                started[b] = e.get("ts", "?")
    for b, ts in started.items():
        if st.get("review-" + b.replace("/", "-"), "").startswith("approved"):
            continue
        if not git(root, "rev-parse", "--verify", "-q", b) or not base:
            continue
        if not [s for s in lines(git(root, "cherry", base, b)) if s.startswith("+ ")]:
            continue  # everything already in base
        yield f"/dk:review trên nhánh {b} chưa APPROVE", f".dk/log: dk:review bắt đầu lúc {ts}, state không có review-{b.replace('/', '-')}: approved"


def main(argv):
    limit, days = 8, 14
    for i, a in enumerate(argv):
        if a == "--max" and i + 1 < len(argv):
            limit = int(argv[i + 1])
        if a == "--days" and i + 1 < len(argv):
            days = int(argv[i + 1])
    top = git(Path.cwd(), "rev-parse", "--show-toplevel")
    root = Path(top) if top else Path.cwd()
    if not (root / ".dk").is_dir():
        return 0
    st, base = state(root), base_ref(root)
    found = [*uncommitted(root), *last_check(root), *evidence(root), *gates(root, st)]
    if base:
        found += [*branches(root, base, days), *reviews(root, st, base)]
    if not found:
        return 0
    print("Dấu hiệu việc bỏ dở - kiểm lại trước khi làm tiếp; khi báo người dùng thì trích đúng bằng chứng dưới đây:")
    for sign, proof in found[:limit]:
        print(f"- {sign}. Bằng chứng: {proof}")
    if len(found) > limit:
        print(f"- … và {len(found) - limit} dấu hiệu khác: python3 <plugin>/scripts/dk-unfinished.py --max 50")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
