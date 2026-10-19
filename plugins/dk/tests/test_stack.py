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
    deploy = { kind = "cloudflare", config = "worker/wrangler.jsonc", health = "/api/health", nonprod_envs = ["staging"] }

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


if __name__ == "__main__":
    unittest.main()
