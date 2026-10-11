#!/usr/bin/env python3
"""Generate docs/db/erd.md (Mermaid erDiagram) from Flyway migrations. Deterministic, no DB needed.

Handles: CREATE TABLE (incl. IF NOT EXISTS, schema-qualified), inline/table-level REFERENCES,
ALTER TABLE ADD COLUMN / DROP COLUMN / ADD CONSTRAINT FOREIGN KEY, DROP TABLE, RENAME. Skips partitions.
Usage: gen-erd.py [migrations_dir] [out_file]
"""
import re
import sys
from pathlib import Path

MIG = Path(sys.argv[1] if len(sys.argv) > 1 else "backend/src/main/resources/db/migration")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/db/erd.md")


def version_key(p: Path):
    m = re.match(r"V(\d+(?:[._]\d+)*)__", p.name)
    return [int(x) for x in re.split(r"[._]", m.group(1))] if m else [10**9]


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

for f in sorted(MIG.glob("V*__*.sql"), key=version_key):
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

lines = ["# Sơ đồ cơ sở dữ liệu", "",
         "> Sinh tự động từ Flyway migrations bằng `gen-erd.sh` — không sửa tay.", "",
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
