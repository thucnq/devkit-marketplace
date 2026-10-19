#!/usr/bin/env python3
"""RED → GREEN evidence per acceptance criterion (idea from ECC tdd-workflow), zero tokens.

Usage: dk-evidence.py red <feature>      after test-author: run the feature's tests first; records which ACs FAIL
       dk-evidence.py red <feature> --compile   tests do not compile yet (missing classes): compile-time RED
       dk-evidence.py green <feature>    after implementation: records which ACs PASS; exit 1 if a mandatory AC is not green
       dk-evidence.py report <feature>   markdown table for the PR body

Reads Surefire XML (backend/target/surefire-reports/TEST-*.xml) and maps test cases to AC ids through the
test name or the @DisplayName("AC-…") above the test method. Writes .dk/evidence/<feature>.json (commit it).
A test that already PASSES at RED did not prove anything: it is flagged so the reviewer looks at it.
With .dk/stack.toml (dk 0.7.0) it reads the JUnit XML of every component instead (pytest --junitxml, vitest
junit reporter, Surefire — all the same format); Python test names may carry the AC in snake case.
"""
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dk_stack import StackError, ac_ids, load as load_stack  # noqa: E402

AC_HEAD = re.compile(r"^###\s+(AC-[A-Z0-9]+-[A-Z0-9]+)")
DISPLAY = re.compile(r'@DisplayName\(\s*"(AC-[A-Z0-9]+-[A-Z0-9]+)[^"]*"\s*\)[\s\S]{0,400}?\bvoid\s+(\w+)\s*\(')
REPORTS = ["backend/target/surefire-reports", "target/surefire-reports"]


def feature_acs(feature):
    f = Path("docs/acceptance") / f"{feature}.md"
    if not f.exists():
        sys.exit(f"dk-evidence: thiếu {f}")
    acs, cur = {}, None
    for line in f.read_text(encoding="utf-8").splitlines():
        m = AC_HEAD.match(line.strip())
        if m:
            cur = m.group(1)
            acs[cur] = {"optional": False}
        elif cur and re.search(r"Ưu tiên\s*:\s*Tùy chọn", line, re.I):
            acs[cur]["optional"] = True
    # tenant/validation tests the test-author adds on top of the written ACs
    prefix = next(iter(acs), "AC-X-01").rsplit("-", 1)[0]
    for extra in ("TENANT", "VALIDATION", "ABUSE"):
        acs.setdefault(f"{prefix}-{extra}", {"optional": True, "implicit": True})
    return acs


def method_map():
    """(class simple name, method) -> AC id, from @DisplayName in test sources."""
    out = {}
    for f in Path(".").glob("**/src/test/**/*.java"):
        if "/target/" in str(f):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in DISPLAY.finditer(text):
            out[(f.stem, m.group(2))] = m.group(1)
    return out


PROFILE = {"on": False}


def report_files():
    try:
        stack = load_stack()
    except StackError as e:
        sys.exit(f"dk-evidence: {e}")
    if stack is None:
        files = [x for d in REPORTS for x in Path(d).glob("TEST-*.xml")]
        if not files:
            sys.exit("dk-evidence: chưa có báo cáo Surefire — chạy test của tính năng trước "
                     "(./mvnw -q -pl backend test -Dtest='*<Feature>*'), kể cả khi đang đỏ")
        return files
    PROFILE["on"] = True
    files = [Path(c.junit) for c in stack.components if Path(c.junit).is_file()]
    files += [x for c in stack.components if c.kind == "java-maven"
              for x in (Path(c.root) / "target" / "surefire-reports").glob("TEST-*.xml")]
    if not files:
        sys.exit("dk-evidence: chưa có báo cáo JUnit (.dk/junit/*.xml) — chạy lệnh test của tính năng trước "
                 "(python3 <plugin>/scripts/dk_stack.py test-cmd <feature>), kể cả khi đang đỏ")
    return files


def run_results():
    mm = method_map()
    res = {}
    files = report_files()
    newest = max(f.stat().st_mtime for f in files)
    # only the latest test run: reports older than 10 minutes before the newest one are leftovers
    files = [f for f in files if f.stat().st_mtime >= newest - 600]
    for f in files:
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for tc in root.iter("testcase"):
            name, cls = tc.get("name", ""), tc.get("classname", "")
            # Surefire: vn.x.CtyApiTest → CtyApiTest; vitest: test/health.test.ts → health.test.ts; pytest: tests.test_x
            cls = cls.rsplit("/", 1)[-1] if "/" in cls else cls.rsplit(".", 1)[-1]
            found = ac_ids(name, python=PROFILE["on"])
            ac = found[0] if found else mm.get((cls, name.split("(")[0]))
            if not ac:
                continue
            status = ("FAIL" if tc.find("failure") is not None or tc.find("error") is not None
                      else "SKIP" if tc.find("skipped") is not None else "PASS")
            prev = res.get(ac)
            # several tests for one AC: the AC is green only if all are green
            if prev is None or status == "FAIL" or (status == "SKIP" and prev["status"] == "PASS"):
                res[ac] = {"status": status, "test": f"{cls}#{name.split('(')[0]}"}
    return res, datetime.fromtimestamp(newest, timezone.utc).isoformat(timespec="seconds")


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("red", "green", "report"):
        sys.exit(__doc__)
    mode, feature = sys.argv[1], sys.argv[2]
    acs = feature_acs(feature)
    path = Path(".dk/evidence") / f"{feature}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    if mode in ("red", "green"):
        if mode == "red" and "--compile" in sys.argv:
            res = {a: {"status": "FAIL", "test": "(không biên dịch)"} for a in acs if not acs[a].get("implicit")}
            ran = datetime.now(timezone.utc).isoformat(timespec="seconds")
        else:
            res, ran = run_results()
        snap = {"ts": ran, "commit": commit(),
                "results": {ac: res[ac] for ac in acs if ac in res}}
        data[mode] = snap
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        r = snap["results"]
        mandatory = [a for a, v in acs.items() if not v["optional"]]
        if mode == "red":
            red = [a for a in r if r[a]["status"] == "FAIL"]
            early = [a for a in r if r[a]["status"] == "PASS"]
            none = [a for a in mandatory if a not in r]
            print(f"dk-evidence RED {feature}: {len(red)} AC đỏ đúng kỳ vọng · {len(early)} AC đã xanh trước khi code"
                  f" · {len(none)} AC bắt buộc chưa có test chạy")
            for a in early:
                print(f"  ⚠ {a} PASS trước khi implement ({r[a]['test']}) — test có thể không kiểm gì; xem lại assert")
            for a in none:
                print(f"  ✗ {a} chưa có test chạy")
            return 1 if none else 0
        notgreen = [a for a in mandatory if r.get(a, {}).get("status") != "PASS"]
        print(f"dk-evidence GREEN {feature}: {sum(1 for a in r if r[a]['status'] == 'PASS')}/{len(r)} AC xanh"
              + (f" · chưa xanh: {', '.join(notgreen)}" if notgreen else ""))
        if "red" not in data:
            print("  ⚠ không có bản ghi RED — không chứng minh được test được viết trước code")
        return 1 if notgreen else 0

    red, green = data.get("red", {}).get("results", {}), data.get("green", {}).get("results", {})
    print(f"### Bằng chứng RED → GREEN — {feature}\n")
    print(f"RED: {data.get('red', {}).get('ts', '—')} @ {data.get('red', {}).get('commit', '—')} · "
          f"GREEN: {data.get('green', {}).get('ts', '—')} @ {data.get('green', {}).get('commit', '—')}\n")
    print("| AC | RED | GREEN | Test |\n|---|---|---|---|")
    icon = {"FAIL": "🔴", "PASS": "🟢", "SKIP": "⏭"}
    for a, v in acs.items():
        if v.get("implicit") and a not in red and a not in green:
            continue
        r, g = red.get(a, {}), green.get(a, {})
        flag = " ⚠ xanh trước khi code" if r.get("status") == "PASS" else ""
        print(f"| {a} | {icon.get(r.get('status'), '—')}{flag} | {icon.get(g.get('status'), '—')} | {g.get('test') or r.get('test') or '❌'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
