"""Regression tests for the zero-token gates (idea from ECC: every hook has a test, run in CI).

Run: python3 -m unittest discover -s plugins/dk/tests -v
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
GUARD = SCRIPTS / "guard.py"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class GuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        r = cls.root = Path(cls.tmp.name)
        git(r, "init", "-q", "-b", "main")
        git(r, "config", "user.email", "t@example.com")
        git(r, "config", "user.name", "t")
        (r / ".dk").mkdir()
        (r / ".dk/state.md").write_text("phase: build\n")
        mig = r / "backend/src/main/resources/db/migration"
        mig.mkdir(parents=True)
        (mig / "V1__init.sql").write_text("create table a(id int);\n")
        (r / "deploy/envs").mkdir(parents=True)
        (r / "deploy/envs/prod.env").write_text("DEPLOY_HOST=prod.khach.vn\n")
        (r / "frontend").mkdir()
        (r / "frontend/eslint.config.js").write_text("export default []\n")
        (r / ".gitleaks.toml").write_text("[extend]\n")
        (r / "pom.xml").write_text("<minimum>0.70</minimum>\n")
        (r / "Foo.java").write_text("class Foo { @Test void a() {} }\n")
        git(r, "add", "-A")
        git(r, "commit", "-qm", "init")
        git(r, "switch", "-q", "-c", "feat/x")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_guard(self, mode, payload, env=None):
        e = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_PLUGIN_OPTION_STRICT_GATES": "false",
             "CLAUDE_PLUGIN_ROOT": str(SCRIPTS.parent)}
        e.pop("DK_ALLOW_QUALITY_EDIT", None)
        e.update(env or {})
        r = subprocess.run(["python3", str(GUARD), mode], input=json.dumps(payload), capture_output=True,
                           text=True, cwd=self.root, env=e)
        return r.returncode, r.stderr

    def bash(self, cmd, **kw):
        return self.run_guard("bash", {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(self.root)}, **kw)[0]

    def file(self, tool, **inp):
        env = inp.pop("env", None)
        return self.run_guard("file", {"tool_name": tool, "tool_input": inp, "cwd": str(self.root)}, env)[0]

    # --- Bash -------------------------------------------------------------------------------------------
    def test_bash_blocks(self):
        for cmd in [
            "cat .env", "cat deploy/envs/prod.env", "gh pr merge 5", "git push origin main",
            'git push origin "main"', 'bash -c "git push origin main"', "git push --force",
            "bash <<'EOF'\ngit push origin main\nEOF", "./deploy.sh prod", "deploy.sh 'prod'",
            "ssh deploy@prod.khach.vn", "bash scripts/dk-state.sh approve spec", "git commit --no-verify -m x",
            "rm -rf /", "sed -i 's/a/b/' frontend/eslint.config.js", "echo '{}' > .gitleaks.toml",
            "cp /tmp/x .gitleaks.toml",
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd), 2)

    def test_bash_allows(self):
        for cmd in [
            "cat deploy/.env.example", "git push -u origin HEAD", "git push origin feat/x",
            'gh pr create --title "docs" --body "sau đó người chạy gh pr merge và git push origin main"',
            "cat > /tmp/pr.md <<'EOF'\nKhông git push origin main, không gh pr merge.\nEOF",
            "echo 'nhắc: gh pr merge do người làm'", "./deploy.sh staging", "ls frontend/eslint.config.js",
            "cat .gitleaks.toml",
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd), 0)

    def test_commit_message_mentioning_push_is_allowed(self):
        self.assertEqual(self.bash('git commit --allow-empty -m "docs: không git push origin main"'), 0)

    def test_push_from_main_blocked(self):
        git(self.root, "switch", "-q", "main")
        try:
            self.assertEqual(self.bash("git push -u origin HEAD"), 2)
        finally:
            git(self.root, "switch", "-q", "feat/x")

    def test_quality_edit_allowed_for_human_session(self):
        self.assertEqual(self.bash("sed -i 's/a/b/' frontend/eslint.config.js", env={"DK_ALLOW_QUALITY_EDIT": "1"}), 0)

    def test_shell_writes_to_state_and_migration(self):
        self.assertEqual(self.bash("echo 'phase: ship' >> .dk/state.md"), 2)
        self.assertEqual(self.bash("sed -i 's/a/b/' backend/src/main/resources/db/migration/V1__init.sql"), 2)
        self.assertEqual(self.bash("bash scripts/dk-state.sh set feature cty"), 0)

    # --- Agent independence -----------------------------------------------------------------------------
    def agent(self, role, mode, tool, inp):
        payload = {"tool_name": tool, "tool_input": inp, "cwd": str(self.root), "agent_id": "a1", "agent_type": f"dk:{role}"}
        return self.run_guard(mode, payload)[0]

    def test_test_author_is_blind(self):
        prod = str(self.root / "backend/src/main/java/vn/x/feature/cty/CtyService.java")
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": prod}), 2)
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": str(self.root / "frontend/src/App.tsx")}), 2)
        self.assertEqual(self.agent("test-author", "file", "Read", {"file_path": str(self.root / "docs/api/openapi.yaml")}), 0)
        self.assertEqual(self.agent("test-author", "file", "Read",
                                    {"file_path": str(self.root / "frontend/src/features/a/A.test.tsx")}), 0)
        self.assertEqual(self.agent("test-author", "file", "Grep", {"pattern": "class"}), 2)
        self.assertEqual(self.agent("test-author", "file", "Grep", {"pattern": "x", "path": "backend/src/main/java"}), 2)
        self.assertEqual(self.agent("test-author", "file", "Grep", {"pattern": "x", "path": "backend/src/test"}), 0)
        self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": "cat backend/src/main/java/vn/x/A.java"}), 2)
        self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": "./mvnw -q -pl backend test-compile"}), 0)
        self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": "grep -rn Service backend/src"}), 2)
        self.assertEqual(self.agent("test-author", "bash", "Bash", {"command": "grep -rn AC-CTY backend/src/test"}), 0)
        self.assertEqual(self.agent("test-author", "file", "Write",
                                    {"file_path": str(self.root / "backend/src/test/java/vn/x/CtyApiTest.java"), "content": "x"}), 0)
        self.assertEqual(self.agent("test-author", "file", "Write", {"file_path": prod, "content": "x"}), 2)
        # the main thread (no agent_id) may read production code
        self.assertEqual(self.file("Read", file_path=prod), 0)

    def test_reviewer_and_doc_sync_scope(self):
        self.assertEqual(self.agent("reviewer", "bash", "Bash", {"command": "cat > .dk/reviews/feat-x.md <<'EOF'\nVERDICT: APPROVE\nEOF"}), 0)
        self.assertEqual(self.agent("reviewer", "bash", "Bash", {"command": "echo x > Foo.java"}), 2)
        self.assertEqual(self.agent("reviewer", "bash", "Bash", {"command": "git checkout main"}), 2)
        self.assertEqual(self.agent("reviewer", "bash", "Bash", {"command": "git diff --stat origin/main...HEAD"}), 0)
        self.assertEqual(self.agent("doc-sync", "file", "Edit", {"file_path": str(self.root / "docs/runbook.md"),
                                                                 "old_string": "a", "new_string": "b"}), 0)
        self.assertEqual(self.agent("doc-sync", "file", "Edit", {"file_path": str(self.root / "Foo.java"),
                                                                 "old_string": "a", "new_string": "b"}), 2)

    # --- File tools -------------------------------------------------------------------------------------
    def test_secret_and_state_files(self):
        self.assertEqual(self.file("Read", file_path=str(self.root / ".env")), 2)
        self.assertEqual(self.file("Read", file_path=str(self.root / "deploy/.env.example")), 0)
        self.assertEqual(self.file("Edit", file_path=str(self.root / ".dk/state.md"), old_string="a", new_string="b"), 2)

    def test_migrations(self):
        mig = self.root / "backend/src/main/resources/db/migration"
        self.assertEqual(self.file("Edit", file_path=str(mig / "V1__init.sql"), old_string="a", new_string="b"), 2)
        self.assertEqual(self.file("Write", file_path=str(mig / "V202610121000__b.sql"), content="create table b();"), 0)

    def test_quality_config_files(self):
        f = str(self.root / "frontend/eslint.config.js")
        self.assertEqual(self.file("Edit", file_path=f, old_string="[]", new_string="[{rules:{}}]"), 2)
        self.assertEqual(self.file("Edit", file_path=f, old_string="[]", new_string="[1]",
                                   env={"DK_ALLOW_QUALITY_EDIT": "1"}), 0)
        self.assertEqual(self.file("Read", file_path=f), 0)

    def test_suppressions(self):
        f = str(self.root / "Foo.java")
        self.assertEqual(self.file("Edit", file_path=f, old_string="@Test", new_string="@Disabled @Test"), 2)
        self.assertEqual(self.file("Edit", file_path=f, old_string="void a", new_string="void b // NOPMD"), 2)
        self.assertEqual(self.file("Edit", file_path=f, old_string="void a", new_string="void renamed"), 0)
        self.assertEqual(self.file("Write", file_path=str(self.root / "frontend/a.test.ts"),
                                   content="it.skip('x', () => {})"), 2)
        self.assertEqual(self.file("Write", file_path=str(self.root / "NOTES.md"), content="đừng dùng @Disabled"), 0)

    def test_pom_weakening(self):
        f = str(self.root / "pom.xml")
        self.assertEqual(self.file("Edit", file_path=f, old_string="<minimum>0.70</minimum>",
                                   new_string="<minimum>0.50</minimum>"), 2)
        self.assertEqual(self.file("Edit", file_path=f, old_string="<minimum>0.70</minimum>",
                                   new_string="<minimum>0.80</minimum>"), 0)
        self.assertEqual(self.file("Edit", file_path=f, old_string="<minimum>0.70</minimum>",
                                   new_string="<minimum>0.70</minimum><skipTests>true</skipTests>"), 2)


if __name__ == "__main__":
    unittest.main()
