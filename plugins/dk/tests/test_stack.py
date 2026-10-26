"""dk 0.7.0 stack profile: dk_stack.py and every script that reads .dk/stack.toml (dk-check, guard, ac-trace,
dk-evidence, check-migrations). Also proves that a project WITHOUT a profile behaves exactly like 0.6.1.

Run: python3 -m unittest discover -s plugins/dk/tests -v
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))
import dk_stack  # noqa: E402

STACK = textwrap.dedent("""\
    schema = 1
    profile = "py-ts-cloudflare"

    [[component]]
    name = "pipeline"
    kind = "python"
    root = "pipeline"
    src_dirs = ["pipeline/src"]
    test_dirs = ["pipeline/tests"]
    read_ok = ["pipeline/pyproject.toml"]

    [[component]]
    name = "worker"
    kind = "ts-worker"
    root = "worker"
    src_dirs = ["worker/src"]
    test_dirs = ["worker/test"]
    migration = { kind = "wrangler-seq", dir = "worker/migrations" }
    deploy = { kind = "cloudflare", config = "worker/wrangler.jsonc", health = "/api/health", nonprod_envs = ["staging"], d1_binding = "DB" }

    [[component]]
    name = "web"
    kind = "react-vite"
    root = "web"
    src_dirs = ["web/src"]
    test_dirs = ["web/src"]
    """)


def sh(cwd, *cmd, env=None, inp=None):
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True, env=env, input=inp)


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(root: Path, stack: str = STACK):
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    for d in ("pipeline/src/pkg", "pipeline/tests", "worker/src", "worker/test", "worker/migrations", "web/src", "docs/acceptance"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / ".dk").mkdir(exist_ok=True)
    (root / ".dk/state.md").write_text("phase: build\n")
    if stack:
        (root / ".dk/stack.toml").write_text(stack)
    (root / "pipeline/src/pkg/graph.py").write_text("def f():\n    return 1\n")
    (root / "pipeline/pyproject.toml").write_text(textwrap.dedent("""\
        [project]
        name = "p"
        dependencies = ["httpx"]

        [tool.ruff]
        line-length = 120

        [tool.coverage.report]
        fail_under = 80
        """))
    (root / "worker/src/index.ts").write_text("export default {}\n")
    (root / "worker/migrations/0001_init.sql").write_text("create table a(id text);\n")
    (root / "web/src/App.tsx").write_text("export const A = 1\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")


class StackLibTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_and_scope(self):
        s = dk_stack.load(self.root)
        self.assertEqual([c.name for c in s.components], ["pipeline", "worker", "web"])
        self.assertTrue(s.prod_code("pipeline/src/pkg/graph.py"))
        self.assertTrue(s.prod_code("web/src/App.tsx"))
        self.assertFalse(s.prod_code("web/src/App.test.tsx"))
        self.assertFalse(s.prod_code("pipeline/tests/test_graph.py"))
        self.assertTrue(s.test_write_ok("pipeline/tests/test_graph.py"))
        self.assertTrue(s.test_write_ok("web/src/features/a/A.test.tsx"))
        self.assertFalse(s.test_write_ok("web/src/App.tsx"))
        self.assertTrue(s.test_read_ok("worker/migrations/0001_init.sql"))
        self.assertTrue(s.test_read_ok("pipeline/pyproject.toml"))
        self.assertFalse(s.test_read_ok("worker/src/index.ts"))

    def test_no_profile_is_none(self):
        (self.root / ".dk/stack.toml").unlink()
        self.assertIsNone(dk_stack.load(self.root))

    def test_invalid_profiles(self):
        for bad, msg in [
            (STACK.replace('name = "web"', 'name = "worker"'), "trùng"),
            (STACK.replace('kind = "react-vite"', 'kind = "cobol"'), "không hỗ trợ"),
            (STACK.replace('nonprod_envs = ["staging"]', 'nonprod_envs = ["staging", "production"]'), "nonprod_envs"),
            (STACK.replace('root = "web"', 'root = "khong-co"'), "không tồn tại"),
            ("schema = 1\n[[component]\n", "cú pháp"),
        ]:
            with self.subTest(msg=msg):
                (self.root / ".dk/stack.toml").write_text(bad)
                with self.assertRaises(dk_stack.StackError) as cm:
                    dk_stack.load(self.root)
                self.assertIn(msg, str(cm.exception))

    def test_ac_ids(self):
        self.assertEqual(dk_stack.ac_ids("it('AC-GAME-01: x')"), ["AC-GAME-01"])
        self.assertEqual(dk_stack.ac_ids("def test_ac_graph_01_doi_xung():", python=True), ["AC-GRAPH-01"])
        self.assertEqual(dk_stack.ac_ids("def test_ac_graph_01_doi_xung():"), [])
        self.assertEqual(dk_stack.ac_ids("test_ac_disc_abuse", python=True), ["AC-DISC-ABUSE"])

    def test_steps_by_changed_files_and_mode(self):
        def steps(mode, files="", *extra):
            r = sh(self.root, "python3", str(SCRIPTS / "dk_stack.py"), "steps", mode, *extra, inp=files)
            self.assertEqual(r.returncode, 0, r.stderr)
            return [tuple(line.split("\t")[:2]) for line in r.stdout.splitlines()]
        self.assertEqual(steps("precommit", "pipeline/src/pkg/graph.py\n"), [("pipeline", "format"), ("pipeline", "lint")])
        self.assertIn(("worker", "test"), steps("precommit-strict", "worker/src/index.ts\n"))
        self.assertEqual(steps("quick", "docs/brd.md\n"), [])
        full = steps("full")
        self.assertIn(("web", "build"), full)
        self.assertIn(("pipeline", "coverage"), full)
        self.assertNotIn(("pipeline", "test"), full)

    def test_test_cmd_filters_by_ac(self):
        r = sh(self.root, "python3", str(SCRIPTS / "dk_stack.py"), "test-cmd", "game")
        lines = dict(line.split("\t")[0::2] for line in r.stdout.splitlines())
        self.assertTrue(lines["pipeline"].endswith("-k ac_game_"))
        self.assertTrue(lines["worker"].endswith("-t AC-GAME-"))


class CheckWithProfileTest(unittest.TestCase):
    """dk-check.sh routes to the components that changed and fails when one of their steps fails."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        stack = STACK.replace('read_ok = ["pipeline/pyproject.toml"]',
                              'read_ok = ["pipeline/pyproject.toml"]\nformat = "true"\nlint = "%s"\ntest = "true"\n'
                              'coverage = { cmd = "true", min = 80 }')
        make_repo(self.root, stack)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, mode, lint_ok=True):
        st = self.root / ".dk/stack.toml"
        st.write_text(st.read_text().replace('lint = "%s"', f'lint = "{"true" if lint_ok else "false"}"'))
        (self.root / "pipeline/src/pkg/graph.py").write_text("def f():\n    return 2\n")
        git(self.root, "add", "-A")
        return sh(self.root, "bash", str(SCRIPTS / "dk-check.sh"), mode)

    def test_profile_routing(self):
        r = self.check("precommit")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("| pipeline lint | PASS |", r.stdout)
        self.assertNotIn("worker", r.stdout)
        self.assertNotIn("backend", r.stdout)

    def test_profile_failure(self):
        r = self.check("precommit", lint_ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("| pipeline lint | **FAIL** |", r.stdout)

    def test_full_traces_feature_and_started_ones(self):
        """Specced-but-unbuilt features (tests on other branches) do not fail /dk:review; the branch's own feature does."""
        acc = self.root / "docs/acceptance"
        acc.joinpath("graph.md").write_text("### AC-GRAPH-01: a\n### AC-GRAPH-02: b\n")
        acc.joinpath("metric.md").write_text("### AC-METRIC-01: a\n")
        (self.root / ".dk/state.md").write_text("phase: build\nfeature: graph\n")
        (self.root / "pipeline/tests/test_graph.py").write_text('def test_ac_graph_01_x():\n    """AC-GRAPH-01: x"""\n')
        r = self.check("full")
        self.assertIn("| AC traceability (graph) | **FAIL** |", r.stdout)       # AC-GRAPH-02 has no test
        self.assertIn("| AC traceability (started features) | **FAIL** |", r.stdout)
        (self.root / "pipeline/tests/test_graph.py").write_text(
            'def test_ac_graph_01_x():\n    """AC-GRAPH-01: x"""\n\n\ndef test_ac_graph_02_y():\n    """AC-GRAPH-02: y"""\n')
        r = self.check("full")
        self.assertIn("| AC traceability (graph) | PASS |", r.stdout)
        self.assertIn("| AC traceability (started features) | PASS |", r.stdout)  # METRIC not started: reported only
        self.assertNotIn("AC traceability (all)", r.stdout)

    def test_broken_profile_fails(self):
        (self.root / ".dk/stack.toml").write_text("schema = 2\n")
        git(self.root, "add", "-A")
        r = sh(self.root, "bash", str(SCRIPTS / "dk-check.sh"), "precommit")
        self.assertEqual(r.returncode, 1)
        self.assertIn("stack profile", r.stdout)


class JavaUnchangedTest(unittest.TestCase):
    """Without .dk/stack.toml the report table is identical to dk 0.6.1 (git history copy of dk-check.sh)."""

    def test_same_table_as_061(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            git(root, "init", "-q", "-b", "main")
            git(root, "config", "user.email", "t@example.com")
            git(root, "config", "user.name", "t")
            (root / "backend/src/main/resources/db/migration").mkdir(parents=True)
            (root / "backend/pom.xml").write_text("<project/>")
            (root / "frontend").mkdir()
            (root / "frontend/package.json").write_text("{}")
            (root / "docs/acceptance").mkdir(parents=True)
            (root / "docs/acceptance/note.md").write_text("### AC-NOTE-01: x\n")
            (root / ".dk").mkdir()
            git(root, "add", "-A")
            git(root, "commit", "-qm", "init")
            (root / "backend/pom.xml").write_text("<project></project>")
            (root / "frontend/package.json").write_text('{"a":1}')
            git(root, "add", "-A")
            # frozen 0.6.1 dk-check.sh next to today's helper scripts: isolates the dk-check.sh change
            old = Path(t) / "old"
            old.mkdir()
            shutil.copy(FIXTURES / "dk-check-0.6.1.sh", old / "dk-check.sh")
            for f in ("ac-trace.py", "check-migrations.sh", "dk_event.py", "dk_stack.py"):
                shutil.copy(SCRIPTS / f, old / f)
            env = {**os.environ, "PATH": "/usr/bin:/bin"}  # no mvn/npm/gitleaks: deterministic SKIP/FAIL rows
            rows = lambda out: [x for x in out.splitlines() if x.startswith("|")]  # noqa: E731
            for mode in ("precommit", "precommit-strict", "quick", "full"):
                with self.subTest(mode=mode):
                    a = rows(sh(root, "bash", str(old / "dk-check.sh"), mode, env=env).stdout)
                    b = rows(sh(root, "bash", str(SCRIPTS / "dk-check.sh"), mode, env=env).stdout)
                    self.assertGreater(len(a), 3)
                    self.assertEqual(a, b)


class GuardProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        make_repo(cls.root)
        git(cls.root, "switch", "-q", "-c", "feat/x")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_guard(self, mode, payload, env=None):
        e = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_PLUGIN_OPTION_STRICT_GATES": "false",
             "CLAUDE_PLUGIN_ROOT": str(SCRIPTS.parent)}
        e.pop("DK_ALLOW_QUALITY_EDIT", None)
        e.update(env or {})
        r = sh(self.root, "python3", str(SCRIPTS / "guard.py"), mode, env=e, inp=json.dumps(payload))
        return r.returncode

    def agent(self, role, mode, tool, inp):
        return self.run_guard(mode, {"tool_name": tool, "tool_input": inp, "cwd": str(self.root),
                                     "agent_id": "a1", "agent_type": f"dk:{role}"})

    def file(self, tool, **inp):
        return self.run_guard("file", {"tool_name": tool, "tool_input": inp, "cwd": str(self.root)})

    def bash(self, cmd):
        return self.run_guard("bash", {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(self.root)})

    def test_test_author_scope_from_profile(self):
        R = lambda p: str(self.root / p)  # noqa: E731
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": R("pipeline/src/pkg/graph.py")}), 2)
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": R("worker/src/index.ts")}), 2)
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": R("web/src/App.tsx")}), 2)
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": R("worker/migrations/0001_init.sql")}), 0)
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": R("web/src/App.test.tsx")}), 0)
        self.assertEqual(self.agent("test-author", "file", "Grep", {"pattern": "x", "path": "pipeline/src"}), 2)
        self.assertEqual(self.agent("test-author", "file", "Grep", {"pattern": "x", "path": "worker"}), 2)
        self.assertEqual(self.agent("test-author", "file", "Grep", {"pattern": "x", "path": "pipeline/tests"}), 0)
        self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": "cat pipeline/src/pkg/graph.py"}), 2)
        self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": "grep -rn x worker"}), 2)
        self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": "python3 -m pytest -q pipeline/tests"}), 0)
        self.assertEqual(self.agent("test-author", "file", "Write",
                                    {"file_path": R("pipeline/tests/test_graph.py"), "content": "x"}), 0)
        self.assertEqual(self.agent("test-author", "file", "Write", {"file_path": R("web/src/A.test.tsx"), "content": "x"}), 0)
        self.assertEqual(self.agent("test-author", "file", "Write", {"file_path": R("web/src/App.tsx"), "content": "x"}), 2)
        # Java layout is NOT what this profile protects
        self.assertEqual(self.agent("test-author", "file", "Write",
                                    {"file_path": R("backend/src/test/java/A.java"), "content": "x"}), 2)

    def test_test_author_may_run_tests(self):
        """lau-meme 2026-10: 188 of 195 agent_blind blocks hit commands that read no production code."""
        ok = [
            f"cd {self.root} && npm --prefix worker run test -- --run 2>&1 | tail -80",
            "cd worker && npx vitest run test/graph.test.ts 2>&1 | tail -30",
            "uv run --directory pipeline pytest -q tests/test_graph.py 2>&1 | tail -15",
            "npm --prefix web run -s typecheck 2>&1 | head -20",
            "mkdir -p web/src/share && cat > web/src/share/share.test.tsx <<'EOF'\nit('AC-SHARE-01: x', () => {})\nEOF",
            "ls web/src web/src/daily worker/test",
            "python3 - <<'EOF'\np = 'worker/test/a.test.ts'\ns = open(p).read()\nprint(s.replace('a', 'b'))\nEOF",
            "grep -rn AC-GRAPH worker/test pipeline/tests docs",
            "awk 'length > 120 {print FILENAME\": \"FNR}' pipeline/tests/test_graph.py",
            # a grep/sed pattern is not a path
            'grep -n "pipeline" docs/api/openapi.yaml | head -50',
            "cd web/src && npm --prefix .. run test -- --run subpath 2>&1 | grep -v '^$' | head -80",
            "cd web/src && sed -n 1,120p daily/daily.ui.test.tsx",
            # listing / searching only test files
            "find web/src worker/test -name '*.test.*' -o -name 'test-utils*'",
            f"cd {self.root}/web && find . -name '*.test.*' -not -path './node_modules/*'",
            "grep -rln consent web/src --include=*.test.tsx --include=*.test.ts",
            "wc -l web/src/daily/*.test.tsx",
            # edits of test files after cd, with ; inside the quoted sed script
            "cd worker/test; sed -i '/^let n = 0$/d;/^  n++$/d' auth.test.ts; grep -n n auth.test.ts",
            "cd pipeline/tests && cat >> test_graph.py <<'E'\ndef test_ac_graph_09_x():\n    pass\nE",
            "python3 - <<'EOF'\ns = open('web/src/art/art.test.tsx').read()\ni = s.index('x')\nEOF",
        ]
        for cmd in ok:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": cmd}), 0)
        blocked = [
            "grep -rln x docs worker/test web/src",
            "cat web/src/App.tsx",
            "cd web/src && cat App.tsx",
            "head -40 worker/src/*.ts",
            "grep -rn x .",
            "python3 - <<'EOF'\nprint(open('worker/src/index.ts').read())\nEOF",
            "cd web/src; ls daily; grep -n -i daily App.tsx",
            "find web/src -name '*.tsx'",
            "grep -rn fetch web/src --include=*.tsx",
            "cd worker/test && sed -i 's/a/b/' ../src/index.ts",
        ]
        for cmd in blocked:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": cmd}), 2)

    def test_test_author_test_infra_inside_src(self):
        """web/src/test/setup.ts is test setup, not production code (blocked 5 times in lau-meme)."""
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": str(self.root / "web/src/test/setup.ts")}), 0)
        self.assertEqual(self.agent("test-author", "file", "Write",
                                    {"file_path": str(self.root / "web/src/test/fixtures.ts"), "content": "x"}), 0)
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": str(self.root / "web/src/testing.ts")}), 2)

    def test_agents_in_a_worktree(self):
        """Paths in a linked worktree are matched relative to that worktree, not the main checkout."""
        with tempfile.TemporaryDirectory() as d:
            wt = Path(d) / "wt"
            git(self.root, "worktree", "add", "-q", "-b", "feat/wt", str(wt))
            try:
                self.assertEqual(self.agent("test-author", "file", "Write",
                                            {"file_path": str(wt / "worker/test/a.test.ts"), "content": "x"}), 0)
                self.assertEqual(self.agent("test-author", "file", "Read",
                                            {"file_path": str(wt / "worker/src/index.ts")}), 2)
                self.assertEqual(self.agent("test-author", "file", "Write",
                                            {"file_path": str(wt / "worker/src/index.ts"), "content": "x"}), 2)
            finally:
                git(self.root, "worktree", "remove", "--force", str(wt))
        nested = self.root / ".claude/worktrees/touch"
        git(self.root, "worktree", "add", "-q", "-b", "feat/touch", str(nested))
        try:
            self.assertEqual(self.agent("test-author", "file", "Write",
                                        {"file_path": str(nested / "web/src/game/touch.ui.test.tsx"), "content": "x"}), 0)
            self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": str(nested / "web/src/App.tsx")}), 2)
        finally:
            git(self.root, "worktree", "remove", "--force", str(nested))

    def test_redirect_parsing(self):
        """`>` inside quoted awk/python text is not a file write (blocked 6 times in lau-meme)."""
        self.assertEqual(self.agent("reviewer", "bash", "Bash",
                                    {"command": "awk '$2 >= 3 {print $1}' .dk/check-report.md"}), 0)
        self.assertEqual(self.agent("reviewer", "bash", "Bash",
                                    {"command": "python3 - <<'EOF'\nif len(x) > 120: print(x)\nEOF"}), 0)
        self.assertEqual(self.agent("reviewer", "bash", "Bash",
                                    {"command": 'grep -rniE "ignore (all )?previous|>>|api[_-]?key" web/src | head'}), 0)
        self.assertEqual(self.agent("doc-sync", "bash", "Bash",
                                    {"command": "S=/tmp/claude-1000/x; git show HEAD:docs/db/erd.md > \"$S/erd.md\""}), 0)
        self.assertEqual(self.agent("doc-sync", "bash", "Bash",
                                    {"command": "git show HEAD:docs/a.md > /tmp/../tmp/a.md"}), 0)
        self.assertEqual(self.agent("reviewer", "bash", "Bash", {"command": "cd worker && echo x > src/a.ts"}), 2)
        self.assertEqual(self.agent("reviewer", "bash", "Bash", {"command": "echo x > worker/src/a.ts"}), 2)
        self.assertEqual(self.agent("reviewer", "bash", "Bash",
                                    {"command": "cat > worker/src/a.ts <<'EOF'\nx\nEOF"}), 2)

    def test_python_suppressions(self):
        p = str(self.root / "pipeline/src/pkg/graph.py")
        for add in ["import os  # noqa: F401", "x = f()  # type: ignore", "@pytest.mark.skip\ndef t(): pass",
                    "if x:  # pragma: no cover\n    pass", "pytest.skip('later')", "@pytest.mark.xfail\ndef t(): pass"]:
            with self.subTest(add=add):
                self.assertEqual(self.file("Edit", file_path=p, old_string="return 1", new_string=f"return 1\n{add}"), 2)
        self.assertEqual(self.file("Edit", file_path=p, old_string="return 1", new_string="return 2"), 0)
        self.assertEqual(self.file("Write", file_path=str(self.root / "docs/note.md"), content="dùng # noqa khi..."), 0)

    def test_pyproject(self):
        p = str(self.root / "pipeline/pyproject.toml")
        self.assertEqual(self.file("Edit", file_path=p, old_string='["httpx"]', new_string='["httpx", "tenacity"]'), 0)
        self.assertEqual(self.file("Edit", file_path=p, old_string="line-length = 120", new_string="line-length = 200"), 2)
        self.assertEqual(self.file("Edit", file_path=p, old_string="fail_under = 80", new_string="fail_under = 10"), 2)
        self.assertEqual(self.file("Edit", file_path=p, old_string="[project]", new_string="[project"), 2)
        self.assertEqual(self.bash("sed -i 's/80/10/' pipeline/pyproject.toml"), 2)

    def test_dev_vars_secret(self):
        self.assertEqual(self.bash("cat worker/.dev.vars"), 2)
        self.assertEqual(self.file("Read", file_path=str(self.root / "worker/.dev.vars.staging")), 2)
        self.assertEqual(self.file("Read", file_path=str(self.root / "worker/.dev.vars.example")), 0)

    def test_quality_files(self):
        for f in ("ruff.toml", "worker/vitest.config.ts", "pytest.ini"):
            path = self.root / f
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x\n")
            with self.subTest(f=f):
                self.assertEqual(self.file("Write", file_path=str(path), content="y"), 2)

    def test_broken_profile_blocks_commit_and_agents(self):
        st = self.root / ".dk/stack.toml"
        good = st.read_text()
        try:
            st.write_text("schema = 1\n")
            self.assertEqual(self.bash("git commit -m x"), 2)
            self.assertEqual(self.agent("test-author", "file", "Read",
                                        {"file_path": str(self.root / "docs/brd.md")}), 2)
        finally:
            st.write_text(good)
        self.assertEqual(self.bash("git status"), 0)


class TraceAndEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_repo(self.root)
        (self.root / "docs/acceptance/graph.md").write_text(textwrap.dedent("""\
            ### AC-GRAPH-01: đối xứng
            Ưu tiên: Bắt buộc
            ### AC-GRAPH-02: không trùng cặp
            Ưu tiên: Bắt buộc
            ### AC-GRAPH-03: BFS
            Ưu tiên: Bắt buộc
            """))
        (self.root / "pipeline/tests/test_graph.py").write_text(
            'def test_ac_graph_01_doi_xung():\n    """đối xứng"""\n\ndef test_ac_graph_03_bfs():\n    pass\n')
        (self.root / "worker/test/graph.test.ts").write_text('it("AC-GRAPH-02: không trùng", () => {})\n')

    def tearDown(self):
        self.tmp.cleanup()

    def test_ac_trace_reads_profile_and_snake_case(self):
        r = sh(self.root, "python3", str(SCRIPTS / "ac-trace.py"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("3/3", r.stdout)

    def junit(self, pytest_fail: bool, vitest_fail: bool):
        d = self.root / ".dk/junit"
        d.mkdir(parents=True, exist_ok=True)
        f = '<failure message="assert"/>' if pytest_fail else ""
        (d / "pipeline.xml").write_text(
            '<testsuites><testsuite name="pytest">'
            f'<testcase classname="tests.test_graph" name="test_ac_graph_01_doi_xung">{f}</testcase>'
            f'<testcase classname="tests.test_graph" name="test_ac_graph_03_bfs">{f}</testcase>'
            '</testsuite></testsuites>')
        g = '<failure message="expected"/>' if vitest_fail else ""
        (d / "worker.xml").write_text(
            '<testsuites name="vitest tests"><testsuite name="test/graph.test.ts">'
            f'<testcase classname="test/graph.test.ts" name="graph &gt; AC-GRAPH-02: không trùng">{g}</testcase>'
            '</testsuite></testsuites>')

    def test_red_green_from_junit(self):
        ev = str(SCRIPTS / "dk-evidence.py")
        self.junit(True, True)
        r = sh(self.root, "python3", ev, "red", "graph")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 AC đỏ", r.stdout)
        self.junit(False, True)
        r = sh(self.root, "python3", ev, "green", "graph")
        self.assertEqual(r.returncode, 1)
        self.assertIn("AC-GRAPH-02", r.stdout)
        self.junit(False, False)
        r = sh(self.root, "python3", ev, "green", "graph")
        self.assertEqual(r.returncode, 0, r.stdout)
        data = json.loads((self.root / ".dk/evidence/graph.json").read_text())
        self.assertEqual(data["green"]["results"]["AC-GRAPH-02"]["status"], "PASS")


class WranglerMigrationsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_repo(self.root)
        git(self.root, "switch", "-q", "-c", "feat/x")

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return sh(self.root, "bash", str(SCRIPTS / "check-migrations.sh"), "--kind", "wrangler-seq",
                  "--dir", "worker/migrations", "main", "HEAD")

    def add(self, name, body="alter table a add column b text;\n"):
        (self.root / "worker/migrations" / name).write_text(body)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", name)

    def test_rules(self):
        self.add("0002_add_b.sql")
        self.assertEqual(self.check().returncode, 0)
        self.add("0003-bad.sql")
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("NNNN_", r.stdout)

    def test_number_must_exceed_base(self):
        self.add("0001_again.sql")
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("không lớn hơn", r.stdout)

    def test_destructive_and_edit(self):
        self.add("0002_drop.sql", "drop table a;\n")
        self.assertEqual(self.check().returncode, 1)
        git(self.root, "reset", "-q", "--hard", "main")
        (self.root / "worker/migrations/0001_init.sql").write_text("create table a(id text, x text);\n")
        git(self.root, "commit", "-qam", "edit")
        self.assertIn("đã commit bị sửa", self.check().stdout)

    def test_flyway_default_unchanged(self):
        r = sh(self.root, "bash", str(SCRIPTS / "check-migrations.sh"), "main", "HEAD")
        self.assertEqual(r.returncode, 0)


@unittest.skipUnless(shutil.which("bash"), "bash required")
class SessionStartTest(unittest.TestCase):
    def test_prints_stack(self):
        with tempfile.TemporaryDirectory() as t:
            make_repo(Path(t))
            r = sh(t, "bash", str(SCRIPTS / "session-start.sh"))
            self.assertIn("stack: py-ts-cloudflare", r.stdout)


class PartTimePlanTest(unittest.TestCase):
    """/dk:plan --hours-per-week: personal projects run part-time; unset keeps the full-time schedule."""

    def plan(self, root, *flags):
        r = sh(root, "python3", str(SCRIPTS / "gen-plan.py"), *flags)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return {i["id"]: i for i in json.loads((root / "docs/plan/plan.json").read_text())["items"]}

    def test_twenty_hours_doubles_duration(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "docs/estimate").mkdir(parents=True)
            (root / "docs/estimate/items.json").write_text(json.dumps({
                "params": {"engineers": 1, "overhead_pct": 0.3, "start_date": "2026-11-02", "holidays": [], "uat_weeks": 0},
                "items": [{"id": "NEN", "name": "Khởi tạo", "points": 3}]}))
            self.assertEqual(self.plan(root)["NEN"]["kh"], ["2026-11-02", "2026-11-05"])             # 3.9 → 4 days
            self.assertEqual(self.plan(root, "--hours-per-week", "20", "--rebaseline")["NEN"]["kh"],
                             ["2026-11-02", "2026-11-11"])                                          # 7.8 → 8 days
            self.assertIn("Giờ/tuần: 20", (root / "docs/plan/tien-do.md").read_text())
            r = sh(root, "python3", str(SCRIPTS / "gen-plan.py"), "--hours-per-week", "0.5")
            self.assertEqual(r.returncode, 1)


class DeployCloudflareTest(unittest.TestCase):
    """deploy-cf.sh with a fake `npx wrangler` and `curl`: records releases, auto-rollback, refuses production."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        make_repo(self.root)
        (self.root / ".gitignore").write_text(".dk/releases/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "ignore")
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.calls = Path(self.tmp.name) / "calls.log"
        (self.bin / "npx").write_text(textwrap.dedent(f"""\
            #!/usr/bin/env bash
            echo "$*" >> {self.calls}
            n=$(grep -c ' deploy --env' {self.calls})
            case "$*" in
              *" deploy --env"*) echo "Uploaded"; echo "  https://demo-staging.acc.workers.dev"; echo "Current Version ID: 0000000$n-aaaa-bbbb" ;;
            esac
            exit 0
            """))
        (self.bin / "curl").write_text(f"#!/usr/bin/env bash\n[ -f {self.tmp.name}/down ] && exit 7 || exit 0\n")
        for f in ("npx", "curl"):
            (self.bin / f).chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "DK_HEALTH_TRIES": "2", "DK_HEALTH_SLEEP": "0"}

    def tearDown(self):
        self.tmp.cleanup()

    def cf(self, *args):
        return sh(self.root, "bash", str(SCRIPTS / "deploy-cf.sh"), *args, env=self.env)

    def test_deploy_record_and_auto_rollback(self):
        r = self.cf("staging")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("d1 migrations apply DB --env staging --remote", self.calls.read_text())
        log = (self.root / ".dk/releases/staging.log").read_text().splitlines()
        self.assertTrue(log[-1].endswith("\tok"))
        self.assertIn("00000001-aaaa-bbbb", log[-1])
        self.assertEqual(self.cf("staging", "--url").stdout.strip(), "https://demo-staging.acc.workers.dev")
        Path(self.tmp.name, "down").write_text("")
        r = self.cf("staging")
        self.assertEqual(r.returncode, 1)
        self.assertIn("rollback 00000001-aaaa-bbbb --env staging -y", self.calls.read_text())
        self.assertTrue((self.root / ".dk/releases/staging.log").read_text().splitlines()[-1].endswith("\trollback"))

    def test_manual_rollback_to_previous_good(self):
        self.cf("staging")
        self.cf("staging")
        r = self.cf("staging", "--rollback")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("rollback 00000001-aaaa-bbbb", self.calls.read_text())

    def test_refuses_production_dirty_tree_and_unknown_env(self):
        self.assertEqual(self.cf("production").returncode, 2)
        self.assertEqual(self.cf("preview").returncode, 2)
        (self.root / "worker/src/index.ts").write_text("export default {x:1}\n")
        r = self.cf("staging")
        self.assertEqual(r.returncode, 1)
        self.assertIn("chưa commit", r.stdout)
        self.assertFalse(self.calls.exists())


class GuardWranglerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        make_repo(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def bash(self, cmd):
        e = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_PLUGIN_ROOT": str(SCRIPTS.parent)}
        return sh(self.root, "python3", str(SCRIPTS / "guard.py"), "bash", env=e,
                  inp=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(self.root)})).returncode

    def test_production_is_human_only(self):
        for cmd in ["npx wrangler deploy", "cd worker && npx wrangler deploy", "npx wrangler deploy --env production",
                    "npx wrangler rollback abc -y", "npx wrangler secret put ADMIN_TOKEN",
                    "npx wrangler d1 migrations apply DB --remote", "npx wrangler d1 execute DB --remote --command 'delete from x'",
                    "npx wrangler versions deploy v1@100%", "npx wrangler d1 time-travel restore DB --env staging",
                    "npx wrangler delete", "bash deploy-cf.sh production"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd), 2)

    def test_staging_and_local_allowed(self):
        for cmd in ["npx wrangler deploy --env staging", "npx wrangler deploy --env=staging", "npx wrangler deploy -e staging",
                    "npx wrangler deploy --dry-run --outdir=dist", "npx wrangler d1 migrations apply DB --local",
                    "npx wrangler d1 execute DB --local --command 'select 1'", "npx wrangler dev",
                    "npx wrangler rollback abc --env staging -y", "npx wrangler tail --env staging",
                    "bash deploy-cf.sh staging", "git commit -m 'docs: wrangler deploy chỉ người làm'"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd), 0)


if __name__ == "__main__":
    unittest.main()
