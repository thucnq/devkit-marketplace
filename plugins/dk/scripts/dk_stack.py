#!/usr/bin/env python3
"""Stack profile (.dk/stack.toml) - the one place that knows which languages a project uses.

No .dk/stack.toml  ⇒ load() returns None and every caller keeps its 0.6.1 behaviour (java-spring).
Bad .dk/stack.toml ⇒ StackError: callers fail closed (dk-check FAIL, guard blocks commits), never silently
fall back to defaults.

CLI (bash callers; tab-separated output, one record per line):
  dk_stack.py validate                       exit 1 + message when the profile is invalid
  dk_stack.py has                            exit 0 when a profile exists
  dk_stack.py steps <mode> [--all]           <component>\t<step>\t<abs cwd>\t<need or ->\t<command>
                                             files changed are read from stdin (one per line) unless --all
  dk_stack.py test-cmd <feature>             <component>\t<abs cwd>\t<command filtered to the feature's ACs>
  dk_stack.py migrations                     <kind>\t<dir>
  dk_stack.py lockfiles                      one path per line (for osv-scanner)
  dk_stack.py semgrep                        semgrep --config flags for the languages in use
  dk_stack.py deploy                         key=value lines of the deploying component
  dk_stack.py info                           human summary (session-start, doctor)
"""
import re
import sys
from pathlib import Path

try:
    import tomllib  # Python ≥ 3.11
except ModuleNotFoundError:  # pragma: no cover - only on very old Python
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        tomllib = None

STACK_FILE = Path(".dk/stack.toml")
KINDS = ("python", "ts-worker", "react-vite", "java-maven")
MIGRATION_KINDS = ("none", "flyway-ts", "wrangler-seq")
DEPLOY_KINDS = ("compose-ssh", "cloudflare")
MODES = ("precommit", "precommit-strict", "quick", "full")

# step -> modes it runs in, per kind. "coverage" replaces "test" in quick/full (same run, with thresholds).
PLAN = {
    "python": {"format": MODES, "lint": MODES, "test": ("precommit-strict",), "coverage": ("quick", "full")},
    "ts-worker": {"lint": MODES, "typecheck": MODES, "test": ("precommit-strict",), "coverage": ("quick", "full"),
                  "build": ("full",)},
    "react-vite": {"lint": MODES, "typecheck": MODES, "test": ("precommit-strict",), "coverage": ("quick", "full"),
                   "build": ("full",)},
    "java-maven": {"test": ("precommit-strict",), "coverage": ("quick", "full")},
}
_VITEST = "npx --no-install vitest run --reporter=default --reporter=junit --outputFile.junit={junit}"
DEFAULTS = {
    "python": {
        "format": "ruff format --check .", "lint": "ruff check .",
        "test": "python3 -m pytest -q --junitxml={junit}",
        "coverage": "python3 -m pytest -q --junitxml={junit} --cov=src --cov-fail-under={min}",
        "test_filter": "-k {feature_snake}", "min": 80, "need": "py:pytest",
        "test_patterns": ("test_*.py", "*_test.py"), "semgrep": "p/python", "lockfiles": ("uv.lock", "requirements.txt"),
    },
    "ts-worker": {
        "lint": "npm run -s lint", "typecheck": "npm run -s typecheck", "test": _VITEST,
        "coverage": _VITEST + " --coverage --coverage.thresholds.lines={min}",
        "build": "npx --no-install wrangler deploy --dry-run --outdir={tmp}",
        "test_filter": "-t AC-{FEATURE}-", "min": 80, "need": "dir:node_modules",
        "test_patterns": ("*.test.ts", "*.spec.ts"), "semgrep": "p/typescript", "lockfiles": ("package-lock.json",),
    },
    "react-vite": {
        "lint": "npm run -s lint", "typecheck": "npm run -s typecheck", "test": _VITEST,
        "coverage": _VITEST + " --coverage --coverage.thresholds.lines={min}", "build": "npm run -s build",
        "test_filter": "-t AC-{FEATURE}-", "min": 70, "need": "dir:node_modules",
        "test_patterns": ("*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx"), "semgrep": "p/react",
        "lockfiles": ("package-lock.json",),
    },
    "java-maven": {
        "test": "mvn -q -B test", "coverage": "mvn -q -B verify", "test_filter": "-Dtest='{Feature}*'",
        "min": 0, "need": "", "test_patterns": ("*.java", "*.kt"), "semgrep": "p/java", "lockfiles": ("pom.xml",),
    },
}
STEP_KEYS = ("format", "lint", "typecheck", "test", "coverage", "build")


class StackError(Exception):
    pass


def _norm(p: str) -> str:
    p = p.replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


class Component:
    def __init__(self, raw: dict, root: Path):
        self.raw = raw
        self.name = raw["name"]
        self.kind = raw["kind"]
        self.d = DEFAULTS[self.kind]
        self.root = _norm(raw.get("root", "."))
        self.src_dirs = [_norm(x) for x in raw.get("src_dirs", [])]
        self.test_dirs = [_norm(x) for x in raw.get("test_dirs", [])]
        self.read_ok = [_norm(x) for x in raw.get("read_ok", [])]
        pats = raw.get("test_glob")
        self.test_patterns = (tuple(pats) if isinstance(pats, list) else (pats,)) if pats else self.d["test_patterns"]
        self.junit = _norm(raw.get("junit", f".dk/junit/{self.name}.xml"))
        cov = raw.get("coverage")
        self.min = cov.get("min", self.d["min"]) if isinstance(cov, dict) else self.d["min"]
        self.migration = raw.get("migration") or {"kind": "none"}
        self.deploy = raw.get("deploy")
        self.repo = root

    def command(self, step: str) -> str:
        if step == "coverage" and isinstance(self.raw.get("coverage"), dict) and "cmd" in self.raw["coverage"]:
            cmd = self.raw["coverage"]["cmd"]
        else:
            cmd = self.raw.get(step, self.d.get(step, ""))
        if not cmd:
            return ""
        return cmd.format(junit=str(self.repo / self.junit), min=self.min,
                          tmp=str(self.repo / ".dk" / "tmp" / self.name))

    def owns(self, rel: str) -> bool:
        rel = _norm(rel)
        return self.root in ("", ".") or rel == self.root or rel.startswith(self.root + "/")

    def is_test_file(self, rel: str) -> bool:
        name = rel.rsplit("/", 1)[-1]
        return any(Path(name).match(p) for p in self.test_patterns)

    def in_dirs(self, rel: str, dirs) -> bool:
        rel = _norm(rel)
        return any(rel == d or rel.startswith(d + "/") for d in dirs)

    def test_globs(self):
        for d in self.test_dirs:
            for p in self.test_patterns:
                yield f"{d}/**/{p}"


class Stack:
    def __init__(self, data: dict, root: Path):
        self.data = data
        self.profile = data.get("profile", "custom")
        self.components = [Component(c, root) for c in data.get("component", [])]
        self.root = root

    # ---- agent scope (guard) ----
    def prod_code(self, rel: str) -> bool:
        rel = _norm(rel)
        for c in self.components:
            if c.in_dirs(rel, c.src_dirs):
                # tests that live next to the code (web/src/**/*.test.tsx) are not production code
                return not (c.is_test_file(rel) or "test-utils" in rel or "/__fixtures__/" in rel)
        return False

    def source_roots(self):
        """Directories whose blanket listing/grep touches production code."""
        out = {"."}
        for c in self.components:
            out.add(c.root)
            for d in c.src_dirs:
                parts = d.split("/")
                out.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
        return out

    def test_write_ok(self, rel: str) -> bool:
        rel = _norm(rel)
        for c in self.components:
            if c.in_dirs(rel, c.test_dirs):
                if c.in_dirs(rel, c.src_dirs):  # tests live next to code: only test files
                    return c.is_test_file(rel) or "test-utils" in rel
                return True
        return False

    def test_read_ok(self, rel: str) -> bool:
        rel = _norm(rel)
        if rel.startswith(("docs/", ".dk/")) or rel in ("docs", ".dk"):
            return True
        for c in self.components:
            mig = _norm(c.migration.get("dir", "")) if c.migration.get("kind") != "none" else ""
            if self.test_write_ok(rel) or c.in_dirs(rel, c.read_ok) or (mig and c.in_dirs(rel, [mig])):
                return True
        return False

    def migrations(self):
        for c in self.components:
            if c.migration.get("kind", "none") != "none":
                yield c.migration["kind"], _norm(c.migration["dir"])

    def deployer(self):
        return next((c for c in self.components if c.deploy), None)


def validate(data: dict, root: Path) -> list:
    errs = []
    if data.get("schema") != 1:
        errs.append("schema phải là 1")
    comps = data.get("component")
    if not isinstance(comps, list) or not comps:
        errs.append("cần ít nhất một [[component]]")
        return errs
    names = set()
    deployers = 0
    for i, c in enumerate(comps):
        where = f"component #{i + 1} ({c.get('name', '?')})"
        for k in ("name", "kind", "root"):
            if not c.get(k):
                errs.append(f"{where}: thiếu `{k}`")
        if c.get("name") in names:
            errs.append(f"{where}: name trùng")
        names.add(c.get("name"))
        if c.get("kind") and c["kind"] not in KINDS:
            errs.append(f"{where}: kind `{c['kind']}` không hỗ trợ ({', '.join(KINDS)})")
        if c.get("root") and not (root / c["root"]).is_dir():
            errs.append(f"{where}: thư mục root `{c['root']}` không tồn tại")
        for key in ("src_dirs", "test_dirs", "read_ok"):
            v = c.get(key, [])
            if not isinstance(v, list):
                errs.append(f"{where}: `{key}` phải là danh sách")
                continue
            for d in v:
                if Path(d).is_absolute() or ".." in Path(d).parts:
                    errs.append(f"{where}: `{key}` chứa đường dẫn ra ngoài repo: {d}")
        if not c.get("src_dirs"):
            errs.append(f"{where}: thiếu `src_dirs` (guard cần biết code production nằm đâu)")
        m = c.get("migration") or {"kind": "none"}
        if m.get("kind", "none") not in MIGRATION_KINDS:
            errs.append(f"{where}: migration.kind `{m.get('kind')}` không hỗ trợ")
        elif m.get("kind", "none") != "none" and not m.get("dir"):
            errs.append(f"{where}: migration thiếu `dir`")
        dep = c.get("deploy")
        if dep:
            deployers += 1
            if dep.get("kind") not in DEPLOY_KINDS:
                errs.append(f"{where}: deploy.kind `{dep.get('kind')}` không hỗ trợ")
            envs = dep.get("nonprod_envs", [])
            if dep.get("kind") == "cloudflare" and not envs:
                errs.append(f"{where}: deploy cloudflare cần `nonprod_envs`")
            bad = [e for e in envs if str(e).lower().startswith("prod")]
            if bad:
                errs.append(f"{where}: nonprod_envs không được chứa {bad}")
    if deployers > 1:
        errs.append("chỉ một component được có `deploy`")
    return errs


def load(root=None):
    """Stack for the project at root, None without .dk/stack.toml, StackError when invalid."""
    root = Path(root or ".")
    f = root / STACK_FILE
    if not f.is_file():
        return None
    if tomllib is None:
        raise StackError("cần Python ≥ 3.11 (tomllib) hoặc gói tomli để đọc .dk/stack.toml")
    try:
        data = tomllib.loads(f.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise StackError(f".dk/stack.toml sai cú pháp: {e}") from e
    errs = validate(data, root)
    if errs:
        raise StackError(".dk/stack.toml không hợp lệ:\n  - " + "\n  - ".join(errs))
    return Stack(data, root.resolve())


AC_DASH = re.compile(r"\bAC-[A-Z0-9]+-[A-Z0-9]+\b")
AC_SNAKE = re.compile(r"(?:^|[^A-Za-z0-9])ac_([a-z0-9]+)_([a-z0-9]+)(?=_|[^A-Za-z0-9]|$)", re.I)


def ac_ids(text: str, python: bool = False) -> list:
    """AC ids in text. Python test names cannot hold dashes: `test_ac_graph_01_x` counts as AC-GRAPH-01."""
    out = AC_DASH.findall(text)
    if python:
        out += [f"AC-{a.upper()}-{b.upper()}" for a, b in AC_SNAKE.findall(text)]
    seen = []
    for a in out:
        if a not in seen:
            seen.append(a)
    return seen


def feature_vars(feature: str) -> dict:
    up = re.sub(r"[^A-Za-z0-9]", "", feature).upper()
    return {"FEATURE": up, "feature_snake": f"ac_{up.lower()}_", "Feature": up[:1] + up[1:].lower()}


def changed_components(stack: Stack, files) -> list:
    files = [f for f in files if f.strip()]
    return [c for c in stack.components if any(c.owns(f) for f in files)]


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    try:
        stack = load()
    except StackError as e:
        print(f"dk-stack: {e}", file=sys.stderr)
        return 1
    if cmd == "has":
        return 0 if stack else 1
    if cmd == "validate":
        print("dk-stack: không có .dk/stack.toml (profile java-spring)" if stack is None
              else f"dk-stack: OK - {stack.profile}, {len(stack.components)} thành phần")
        return 0
    if stack is None:
        print("dk-stack: không có .dk/stack.toml", file=sys.stderr)
        return 3
    if cmd == "info":
        print(f"stack: {stack.profile} · " + ", ".join(f"{c.name} ({c.kind}, {c.root})" for c in stack.components))
        return 0
    if cmd == "steps":
        mode = argv[1] if len(argv) > 1 else "quick"
        if mode not in MODES:
            print(f"dk-stack: mode {mode} không hợp lệ", file=sys.stderr)
            return 2
        comps = stack.components if ("--all" in argv or mode == "full") else changed_components(stack, sys.stdin.read().splitlines())
        for c in comps:
            for step in STEP_KEYS:
                if mode not in PLAN[c.kind].get(step, ()):
                    continue
                command = c.command(step)
                if command:
                    need = (c.d["need"] if (c.kind != "python" or step in ("test", "coverage")) else "") or "-"
                    print("\t".join([c.name, step, str(stack.root / c.root), need, command]))
        return 0
    if cmd == "test-cmd":
        if len(argv) < 2:
            return 2
        v = feature_vars(argv[1])
        for c in stack.components:
            flt = c.raw.get("test_filter", c.d["test_filter"]).format(**v)
            cmd = c.command("test")
            venv_py = stack.root / c.root / ".venv" / "bin" / "python"
            if c.kind == "python" and venv_py.exists() and cmd.startswith("python3 "):
                cmd = f"{venv_py} {cmd[len('python3 '):]}"
            print("\t".join([c.name, str(stack.root / c.root), f"{cmd} {flt}".strip()]))
        return 0
    if cmd == "migrations":
        for kind, d in stack.migrations():
            print(f"{kind}\t{d}")
        return 0
    if cmd == "lockfiles":
        for c in stack.components:
            for lf in c.d["lockfiles"]:
                p = Path(c.root) / lf
                if p.is_file():
                    print(_norm(str(p)))
        return 0
    if cmd == "semgrep":
        cfgs = []
        for c in stack.components:
            if c.d["semgrep"] not in cfgs:
                cfgs.append(c.d["semgrep"])
        print(" ".join(f"--config {x}" for x in cfgs + ["p/secrets", "p/owasp-top-ten"]))
        return 0
    if cmd == "deploy":
        c = stack.deployer()
        if not c:
            return 1
        print(f"component={c.name}")
        print(f"root={c.root}")
        for k, v in c.deploy.items():
            print(f"{k}={' '.join(v) if isinstance(v, list) else v}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
