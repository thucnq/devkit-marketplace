"""Tests for deterministic scripts: dk-evidence (RED → GREEN), check-migrations, ac-trace --started-only, gen-plan, gen-erd."""
import json
import os
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def sh(cwd, *cmd, check=False):
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True, check=check)


def surefire(root, cases, age=0):
    d = root / "backend/target/surefire-reports"
    d.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f'<testcase name="{n}" classname="vn.x.feature.cty.CtyApiTest">{"<failure/>" if s == "FAIL" else ""}</testcase>'
        for n, s in cases)
    f = d / "TEST-vn.x.feature.cty.CtyApiTest.xml"
    f.write_text(f"<testsuite>{body}</testsuite>")
    if age:
        t = time.time() - age
        os.utime(f, (t, t))


class EvidenceTest(unittest.TestCase):
    def test_red_then_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            sh(r, "git", "init", "-q")
            (r / "docs/acceptance").mkdir(parents=True)
            (r / "docs/acceptance/cty.md").write_text(textwrap.dedent("""\
                ### AC-CTY-01: Tạo công ty
                ### AC-CTY-02: Sửa công ty
                ### AC-CTY-03: Ẩn công ty
                - Ưu tiên: Tùy chọn
                """))
            t = r / "backend/src/test/java/vn/x/feature/cty"
            t.mkdir(parents=True)
            (t / "CtyApiTest.java").write_text(textwrap.dedent("""\
                class CtyApiTest {
                  @Test @DisplayName("AC-CTY-01: tạo") void createsCompany() {}
                  @Test @DisplayName("AC-CTY-02: sửa") void updatesCompany() {}
                }"""))
            ev = str(SCRIPTS / "dk-evidence.py")
            surefire(r, [("createsCompany", "FAIL"), ("updatesCompany", "PASS")])
            red = sh(r, "python3", ev, "red", "cty")
            self.assertEqual(red.returncode, 0, red.stdout + red.stderr)
            self.assertIn("AC-CTY-02 PASS trước khi implement", red.stdout)
            surefire(r, [("createsCompany", "PASS"), ("updatesCompany", "FAIL")])
            self.assertEqual(sh(r, "python3", ev, "green", "cty").returncode, 1)
            surefire(r, [("createsCompany", "PASS"), ("updatesCompany", "PASS")])
            self.assertEqual(sh(r, "python3", ev, "green", "cty").returncode, 0)
            rep = sh(r, "python3", ev, "report", "cty").stdout
            self.assertIn("| AC-CTY-01 | 🔴 | 🟢 |", rep)
            self.assertIn("⚠ xanh trước khi code", rep)
            data = json.loads((r / ".dk/evidence/cty.json").read_text())
            self.assertEqual(set(data), {"red", "green"})

    def test_compile_red_and_missing_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            (r / "docs/acceptance").mkdir(parents=True)
            (r / "docs/acceptance/cty.md").write_text("### AC-CTY-01: Tạo\n")
            out = sh(r, "python3", str(SCRIPTS / "dk-evidence.py"), "red", "cty", "--compile")
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertIn("1 AC đỏ", out.stdout)


class MigrationTest(unittest.TestCase):
    def test_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            for c in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
                sh(r, "git", *c, check=True)
            d = r / "backend/src/main/resources/db/migration"
            d.mkdir(parents=True)
            (d / "V1__init.sql").write_text("create table a(id int);\n")
            sh(r, "git", "add", "-A", check=True)
            sh(r, "git", "commit", "-qm", "base", check=True)
            base = sh(r, "git", "rev-parse", "HEAD").stdout.strip()
            (d / "V202610121000__add_b.sql").write_text("create table b(id int); -- drop later\n")
            sh(r, "git", "add", "-A", check=True)
            sh(r, "git", "commit", "-qm", "ok", check=True)
            ok = sh(r, "bash", str(SCRIPTS / "check-migrations.sh"), base, "HEAD")
            self.assertEqual(ok.returncode, 0, ok.stdout)
            (d / "V202610121100__bad.sql").write_text("alter table a drop column x;\n")
            (d / "V3__name.sql").write_text("create table c(id int);\n")
            (d / "V1__init.sql").write_text("create table a(id int, n text);\n")
            sh(r, "git", "add", "-A", check=True)
            sh(r, "git", "commit", "-qm", "bad", check=True)
            bad = sh(r, "bash", str(SCRIPTS / "check-migrations.sh"), base, "HEAD")
            self.assertEqual(bad.returncode, 1)
            for frag in ("V1__init.sql: migration đã commit", "V202610121100__bad.sql chứa", "V3__name.sql: tên"):
                self.assertIn(frag, bad.stdout)


class TraceAndPlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.r = Path(self.tmp.name)
        (r / "docs/acceptance").mkdir(parents=True)
        (r / "docs/acceptance/cty.md").write_text("### AC-CTY-01: Tạo\n### AC-CTY-02: Sửa\n")
        (r / "docs/acceptance/nd.md").write_text("### AC-ND-01: Mời\n")
        (r / "backend/src/test/java").mkdir(parents=True)
        (r / "backend/src/test/java/T.java").write_text("// AC-CTY-01\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_started_only(self):
        tr = str(SCRIPTS / "ac-trace.py")
        self.assertEqual(sh(self.r, "python3", tr).returncode, 1)
        out = sh(self.r, "python3", tr, "--started-only")
        self.assertEqual(out.returncode, 1)          # CTY started, AC-CTY-02 missing
        self.assertIn("not started", out.stdout)
        self.assertNotIn("AC-ND-01", out.stdout.split("not started")[0])

    def test_started_only_planned_items(self):
        """An AC added to a started file but scheduled by exact id under an unstarted item is not enforced yet."""
        tr = str(SCRIPTS / "ac-trace.py")
        (self.r / "backend/src/test/java/T.java").write_text("// AC-CTY-01 AC-ND-01\n")
        (self.r / "docs/estimate").mkdir(parents=True)
        items = {"items": [{"id": "CTY", "ac": ["AC-CTY-01"]}, {"id": "CTY2", "ac": ["AC-CTY-01", "AC-CTY-02"]}]}
        (self.r / "docs/estimate/items.json").write_text(json.dumps(items))
        out = sh(self.r, "python3", tr, "--started-only")
        self.assertEqual(out.returncode, 0, out.stdout)           # AC-CTY-01 is shared, so CTY2 has not started
        self.assertIn("planned (not enforced yet): AC-CTY-02 (CTY2)", out.stdout)
        self.assertEqual(sh(self.r, "python3", tr).returncode, 1)  # /dk:review still needs every AC
        items["items"][1]["ac"].append("AC-ND-01")                 # an AC only CTY2 lists is tested ⇒ started
        (self.r / "docs/estimate/items.json").write_text(json.dumps(items))
        out = sh(self.r, "python3", tr, "--started-only")
        self.assertEqual(out.returncode, 1)
        self.assertIn("MISSING AC-CTY-02", out.stdout)
        (self.r / "docs/estimate/items.json").write_text(json.dumps({"items": [{"id": "CTY", "ac": ["AC-CTY"]}]}))
        self.assertEqual(sh(self.r, "python3", tr, "--started-only").returncode, 1)  # prefix does not schedule

    def test_gen_plan(self):
        (self.r / "docs/estimate").mkdir(parents=True)
        (self.r / "docs/estimate/items.json").write_text(json.dumps({
            "title": "BÁO GIÁ X", "params": {"engineers": 2, "overhead_pct": 0.3, "start_date": "2026-11-02",
                                             "holidays": [], "uat_weeks": 1},
            "items": [{"id": "NEN", "module": "Nền tảng", "name": "Khởi tạo", "points": 3},
                      {"id": "CTY", "module": "A", "name": "Công ty", "points": 6, "deps": ["NEN"], "ac": ["AC-CTY"]},
                      {"id": "ND", "module": "A", "name": "Người dùng", "points": 2, "deps": ["NEN"]},
                      {"id": "UAT", "module": "B", "name": "Sửa lỗi", "points": 1, "deps": ["*"]}]}))
        out = sh(self.r, "python3", str(SCRIPTS / "gen-plan.py"))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        plan = {i["id"]: i for i in json.loads((self.r / "docs/plan/plan.json").read_text())["items"]}
        self.assertEqual(plan["NEN"]["kh"], ["2026-11-02", "2026-11-05"])      # 3 × 1.3 → 4 working days
        self.assertEqual(plan["CTY"]["kh"][0], "2026-11-06")                   # after NEN
        self.assertGreater(plan["UAT"]["kh"][0], max(plan["CTY"]["kh"][1], plan["ND"]["kh"][1]))
        md = (self.r / "docs/plan/tien-do.md").read_text()
        self.assertIn("AC-CTY-01", md)
        # human ticks AC-CTY-01 → CTY becomes 50% (theo AC)
        (self.r / "docs/plan/tien-do.md").write_text(md.replace("  - [ ] AC-CTY-01", "  - [x] AC-CTY-01"))
        sh(self.r, "python3", str(SCRIPTS / "gen-plan.py"), check=True)
        plan = {i["id"]: i for i in json.loads((self.r / "docs/plan/plan.json").read_text())["items"]}
        self.assertEqual(plan["CTY"]["pct"], 50)
        self.assertEqual(plan["NEN"]["kh"], ["2026-11-02", "2026-11-05"])      # baseline frozen
        self.assertTrue((self.r / "docs/plan/gantt.html").read_text().count("AC-CTY-01") >= 1)



class DeployRollbackTest(unittest.TestCase):
    def test_rollback_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp) / "app"
            host = Path(tmp) / "host"
            bin_ = Path(tmp) / "bin"
            for d in (r / "deploy/envs", host, bin_):
                d.mkdir(parents=True)
            (r / "deploy/envs/staging.env").write_text(f"DEPLOY_HOST=local\nDEPLOY_DIR={host}\nPUBLIC_URL=http://x\n")
            (host / "releases.log").write_text("2026-10-01T00:00:00Z aaa111 deploy\n2026-10-02T00:00:00Z bbb222 deploy\n")
            (bin_ / "docker").write_text(f"#!/bin/sh\necho \"TAG=$TAG $*\" >> {tmp}/docker.log\n")
            (bin_ / "curl").write_text("#!/bin/sh\nexit 0\n")
            for f in ("docker", "curl"):
                (bin_ / f).chmod(0o755)
            env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}"}
            out = subprocess.run(["bash", str(SCRIPTS / "deploy.sh"), "staging", "--rollback"], cwd=r, env=env,
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertIn("TAG=aaa111 compose up -d", (Path(tmp) / "docker.log").read_text())
            self.assertTrue((host / "releases.log").read_text().strip().endswith("aaa111 rollback"))
            prod = subprocess.run(["bash", str(SCRIPTS / "deploy.sh"), "production"], cwd=r, capture_output=True, text=True)
            self.assertEqual(prod.returncode, 2)


class GenErdTest(unittest.TestCase):
    def _mig(self, r):
        d = r / "worker/migrations"
        d.mkdir(parents=True)
        (d / "0001_init.sql").write_text("CREATE TABLE a (id TEXT PRIMARY KEY, n INTEGER NOT NULL);")
        (d / "0002_b.sql").write_text("CREATE TABLE b (id TEXT PRIMARY KEY, a_id TEXT REFERENCES a (id));")
        return d

    def test_sequential_migrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            self._mig(r)
            p = sh(r, "python3", str(SCRIPTS / "gen-erd.py"), "worker/migrations", "erd.md")
            self.assertEqual(p.returncode, 0, p.stderr)
            out = (r / "erd.md").read_text()
            self.assertIn("a ||--o{ b", out)
            self.assertIn("integer n", out)

    def test_no_migrations_leaves_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            (r / "erd.md").write_text("hand drawn")
            p = sh(r, "python3", str(SCRIPTS / "gen-erd.py"), "nowhere", "erd.md")
            self.assertEqual(p.returncode, 1)
            self.assertEqual((r / "erd.md").read_text(), "hand drawn")

    def test_check_reports_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            self._mig(r)
            (r / "erd.md").write_text("```mermaid\nerDiagram\n  a {\n    TEXT id PK\n  }\n  c {\n    TEXT id\n  }\n```\n")
            p = sh(r, "python3", str(SCRIPTS / "gen-erd.py"), "--check", "worker/migrations", "erd.md")
            self.assertEqual(p.returncode, 1)
            self.assertIn("`a` thiếu cột `n`", p.stdout)
            self.assertIn("thiếu bảng `b`", p.stdout)
            self.assertIn("bảng `c` không có trong migrations", p.stdout)
            (r / "erd.md").write_text("  a {\n    TEXT id PK\n    INTEGER n\n  }\n  b {\n    TEXT id\n    TEXT a_id FK\n  }\n")
            p = sh(r, "python3", str(SCRIPTS / "gen-erd.py"), "--check", "worker/migrations", "erd.md")
            self.assertEqual(p.returncode, 0, p.stdout)


class UnfinishedTest(unittest.TestCase):
    """dk-unfinished.py: each sign of abandoned work comes with its evidence; a clean project prints nothing."""

    def _repo(self, tmp):
        remote, r = Path(tmp) / "remote.git", Path(tmp) / "app"
        sh(tmp, "git", "init", "-q", "--bare", "-b", "main", str(remote), check=True)
        r.mkdir()
        for c in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                  ["remote", "add", "origin", str(remote)]):
            sh(r, "git", *c, check=True)
        (r / ".dk").mkdir()
        (r / ".dk/state.md").write_text("# dk state\nphase: build\n")
        (r / "docs/api").mkdir(parents=True)
        (r / "docs/api/openapi.yaml").write_text("openapi: 3.1.0\n")
        self._commit(r, "init")
        sh(r, "git", "push", "-q", "-u", "origin", "main", check=True)
        sh(r, "git", "remote", "set-head", "origin", "main", check=True)
        return r

    def _commit(self, r, msg, f="f.txt"):
        with open(r / f, "a") as fh:
            fh.write(msg + "\n")
        sh(r, "git", "add", "-A", check=True)
        sh(r, "git", "commit", "-q", "-m", msg, check=True)
        return sh(r, "git", "rev-parse", "--short", "HEAD").stdout.strip()

    def _run(self, r):
        p = sh(r, "python3", str(SCRIPTS / "dk-unfinished.py"), "--max", "20")
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_clean_project_prints_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._repo(tmp)
            (r / ".dk/log").mkdir()
            (r / ".dk/log/t.jsonl").write_text("{}\n")  # changes under .dk/ are bookkeeping, not work
            self.assertEqual(self._run(r), "")

    def test_branch_signs_quote_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._repo(tmp)
            sh(r, "git", "switch", "-q", "-c", "feat/local", check=True)
            local = self._commit(r, "feat: chưa push")
            sh(r, "git", "switch", "-q", "-c", "feat/pushed", "main", check=True)
            pushed = self._commit(r, "feat: đã push")
            sh(r, "git", "push", "-q", "-u", "origin", "feat/pushed", check=True)
            # PR #7 merged, then one more commit stayed on the branch (the PR #135 case)
            sh(r, "git", "switch", "-q", "-c", "fix/late", "main", check=True)
            self._commit(r, "fix: phần đầu")
            sh(r, "git", "switch", "-q", "main", check=True)
            sh(r, "git", "merge", "-q", "--no-ff", "-m", "Merge pull request #7 from o/fix/late", "fix/late", check=True)
            sh(r, "git", "push", "-q", "origin", "main", check=True)
            sh(r, "git", "switch", "-q", "fix/late", check=True)
            late = self._commit(r, "ci: commit đến sau")
            # a branch whose only commit was cherry-picked into main is done
            sh(r, "git", "switch", "-q", "-c", "fix/picked", "main", check=True)
            picked = self._commit(r, "fix: đã cherry-pick", f="g.txt")
            sh(r, "git", "switch", "-q", "main", check=True)
            sh(r, "git", "cherry-pick", picked, check=True)
            sh(r, "git", "push", "-q", "origin", "main", check=True)
            out = self._run(r)
            self.assertIn("nhánh feat/local: 1 commit chưa push. Bằng chứng: commit cuối", out)
            self.assertIn(f"{local} feat: chưa push", out)
            self.assertIn("nhánh feat/pushed: 1 commit đã push nhưng chưa vào origin/main (kiểm PR)", out)
            self.assertIn(pushed, out)
            self.assertIn("nhánh fix/late: PR #7 đã merge", out)
            self.assertIn(f"{late} ci: commit đến sau", out)
            self.assertNotIn("fix/picked", out)

    def test_check_evidence_gate_review_and_uncommitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._repo(tmp)
            sh(r, "git", "switch", "-q", "-c", "feat/x", check=True)
            approved = sh(r, "git", "rev-parse", "--short", "HEAD").stdout.strip()
            (r / ".dk/state.md").write_text(f"phase: build\ncontract: approved 2026-10-27 by t at {approved}\n")
            drift = self._commit(r, "design: đổi contract sau khi duyệt", f="docs/api/openapi.yaml")
            head = sh(r, "git", "rev-parse", "--short", "HEAD").stdout.strip()
            (r / ".dk/check-report.md").write_text(
                f"FAIL · quick · 2026-10-27 12:50:27 · {head}\n\n| Check | Result |\n|---|---|\n"
                "| web lint | PASS |\n| web coverage | **FAIL** |\n")
            (r / ".dk/evidence").mkdir()
            (r / ".dk/evidence/cty.json").write_text(json.dumps({"red": {"ts": "2026-10-27T11:00", "commit": "abc1234"}}))
            (r / ".dk/log").mkdir()
            (r / ".dk/log/t.jsonl").write_text(json.dumps(
                {"ts": "2026-10-27T12:50:27+00:00", "branch": "feat/x", "cmd": "dk:review", "ev": "prompt"}) + "\n")
            (r / "src.py").write_text("x = 1\n")
            out = self._run(r)
            self.assertIn("thay đổi chưa commit. Bằng chứng: git status: ?? src.py", out)
            self.assertIn('.dk/check-report.md: "FAIL · quick · 2026-10-27 12:50:27', out)
            self.assertIn("đỏ: web coverage", out)
            self.assertNotIn("HEAD đã đổi", out)
            self.assertIn("tính năng cty: có RED, chưa có GREEN. Bằng chứng: .dk/evidence/cty.json: red lúc 2026-10-27T11:00", out)
            self.assertIn(f"docs/api/openapi.yaml đổi sau khi duyệt cổng contract ({approved}). Bằng chứng: {drift}", out)
            self.assertIn("/dk:review trên nhánh feat/x chưa APPROVE. Bằng chứng: .dk/log: dk:review bắt đầu lúc 2026-10-27T12:50:27", out)
            (r / ".dk/state.md").write_text("phase: build\nreview-feat-x: approved\n")
            self.assertNotIn("/dk:review trên nhánh feat/x", self._run(r))


if __name__ == "__main__":
    unittest.main()
