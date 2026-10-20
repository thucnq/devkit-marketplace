#!/usr/bin/env python3
"""Generate docs/db/erd.md (Mermaid erDiagram) from SQL migrations. Deterministic, no DB needed.

Migrations: Flyway `V<n>__*.sql` or sequential `NNNN_*.sql` (wrangler-seq, Cloudflare D1). Without a
migrations_dir it uses the first `migration.dir` of `.dk/stack.toml`, else the Flyway default.
Handles: CREATE TABLE (incl. IF NOT EXISTS, schema-qualified), inline/table-level REFERENCES,
ALTER TABLE ADD COLUMN / DROP COLUMN / ADD CONSTRAINT FOREIGN KEY, DROP TABLE, RENAME. Skips partitions.
No migration file found ⇒ exit 1 and out_file is left untouched.

--check: write nothing; exit 1 if out_file's diagram misses a table/column of the migrations or lists
a table they do not have. For hand-drawn ERDs (wrangler-seq: D1 has few FKs, relations are drawn by hand).
Usage: gen-erd.py [--check] [migrations_dir] [out_file]
"""
import re
import subprocess
import sys
from pathlib import Path

ARGS = [a for a in sys.argv[1:] if a != "--check"]
CHECK = "--check" in sys.argv[1:]
FLYWAY_DEFAULT = "backend/src/main/resources/db/migration"


def stack_migration_dir():
    try:
        out = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "dk_stack.py"), "migrations"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    line = next((ln for ln in out.splitlines() if "\t" in ln), None)
    return line.split("\t", 1)[1] if line else None


MIG = Path(ARGS[0] if ARGS else (stack_migration_dir() or FLYWAY_DEFAULT))
OUT = Path(ARGS[1] if len(ARGS) > 1 else "docs/db/erd.md")


def version_key(p: Path):
    m = re.match(r"V(\d+(?:[._]\d+)*)__", p.name) or re.match(r"(\d+)_", p.name)
    return [int(x) for x in re.split(r"[._]", m.group(1))] if m else [10**9]


def migration_files():
    return sorted({*MIG.glob("V*__*.sql"), *MIG.glob("[0-9]*_*.sql")}, key=version_key)


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    return re.sub(r"--[^\n]*", "", sql)


def split_top(body: str):
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip()); cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def name(n: str) -> str:
    return n.split(".")[-1].strip('"').lower()


tables: dict[str, dict] = {}
rels: set[tuple[str, str, str]] = set()
KEYWORDS = ("constraint", "primary", "foreign", "unique", "check", "exclude", "like")

FILES = migration_files()
if not FILES:
    print(f"gen-erd: không thấy migration nào trong {MIG} (V<n>__*.sql hoặc NNNN_*.sql) - {OUT} giữ nguyên",
          file=sys.stderr)
    sys.exit(1)

for f in FILES:
    sql = strip_comments(f.read_text(encoding="utf-8"))
    for stmt in sql.split(";"):
        s = " ".join(stmt.split())
        m = re.match(r"(?i)create table (?:if not exists )?([\w.\"]+)\s*\((.*)\)(.*)$", s)
        if m:
            t, body, tail = name(m.group(1)), m.group(2), m.group(3)
            if re.search(r"(?i)partition of", s):
                continue
            cols = tables.setdefault(t, {"cols": {}, "pk": set()})
            for part in split_top(body):
                low = part.lower()
                if low.startswith(KEYWORDS):
                    pk = re.search(r"(?i)primary key\s*\(([^)]*)\)", part)
                    if pk:
                        cols["pk"].update(c.strip().strip('"') for c in pk.group(1).split(","))
                    fk = re.search(r"(?i)foreign key\s*\(([^)]*)\)\s*references\s+([\w.\"]+)", part)
                    if fk:
                        rels.add((name(fk.group(2)), t, fk.group(1).strip()))
                    continue
                toks = part.split()
                if len(toks) < 2:
                    continue
                c, typ = toks[0].strip('"'), toks[1].lower().split("(")[0]
                cols["cols"][c] = typ
                if "primary key" in low:
                    cols["pk"].add(c)
                ref = re.search(r"(?i)references\s+([\w.\"]+)", part)
                if ref:
                    rels.add((name(ref.group(1)), t, c))
            continue
        m = re.match(r"(?i)alter table (?:if exists )?(?:only )?([\w.\"]+) (.*)$", s)
        if m and name(m.group(1)) in tables:
            t, rest = name(m.group(1)), m.group(2)
            for action in split_top(rest):
                a = re.match(r"(?i)add column (?:if not exists )?(\"?\w+\"?) (\w+)", action)
                if a:
                    tables[t]["cols"][a.group(1).strip('"')] = a.group(2).lower()
                    ref = re.search(r"(?i)references\s+([\w.\"]+)", action)
                    if ref:
                        rels.add((name(ref.group(1)), t, a.group(1).strip('"')))
                d = re.match(r"(?i)drop column (?:if exists )?(\"?\w+\"?)", action)
                if d:
                    tables[t]["cols"].pop(d.group(1).strip('"'), None)
                fk = re.search(r"(?i)foreign key\s*\(([^)]*)\)\s*references\s+([\w.\"]+)", action)
                if fk:
                    rels.add((name(fk.group(2)), t, fk.group(1).strip()))
                r = re.match(r"(?i)rename column (\w+) to (\w+)", action)
                if r and r.group(1) in tables[t]["cols"]:
                    tables[t]["cols"][r.group(2)] = tables[t]["cols"].pop(r.group(1))
            continue
        m = re.match(r"(?i)drop table (?:if exists )?([\w.\", ]+)", s)
        if m:
            for t in m.group(1).split(","):
                tables.pop(name(t), None)

if CHECK:
    if not OUT.is_file():
        print(f"gen-erd --check: thiếu {OUT}", file=sys.stderr)
        sys.exit(1)
    drawn: dict[str, set] = {}
    cur = None
    for raw in OUT.read_text(encoding="utf-8").splitlines():
        ln = raw.strip()
        m = re.match(r"([\w.\"]+)\s*\{$", ln)
        if m:
            cur = drawn.setdefault(name(m.group(1)), set())
        elif ln == "}":
            cur = None
        elif cur is not None and len(ln.split()) >= 2:
            cur.add(ln.split()[1].strip('"'))
    drift = [f"thiếu bảng `{t}`" for t in sorted(tables) if t not in drawn]
    drift += [f"`{t}` thiếu cột `{c}`" for t in sorted(tables) if t in drawn
              for c in tables[t]["cols"] if c not in drawn[t]]
    drift += [f"bảng `{t}` không có trong migrations" for t in sorted(drawn) if t not in tables]
    for d in drift:
        print(f"gen-erd --check: {OUT}: {d}")
    print(f"gen-erd --check: {len(tables)} tables, {len(drift)} drift")
    sys.exit(1 if drift else 0)

lines = ["# Sơ đồ cơ sở dữ liệu", "",
         "> Sinh tự động từ SQL migrations bằng `gen-erd.sh` - không sửa tay.", "",
         "```mermaid", "erDiagram"]
for t in sorted(tables):
    lines.append(f"    {t} {{")
    for c, typ in tables[t]["cols"].items():
        flags = []
        if c in tables[t]["pk"]:
            flags.append("PK")
        if any(r[1] == t and r[2] == c for r in rels):
            flags.append("FK")
        safe_typ = re.sub(r"[^\w]", "_", typ)
        suffix = (" " + ",".join(flags)) if flags else ""
        lines.append(f"        {safe_typ} {c}{suffix}")
    lines.append("    }")
for parent, child, col in sorted(rels):
    if parent in tables and child in tables:
        lines.append(f'    {parent} ||--o{{ {child} : "{col}"')
lines.append("```")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"gen-erd: {len(tables)} tables, {len(rels)} relations → {OUT}")
