#!/usr/bin/env python3
"""PreToolUse guard for the dk plugin. Zero tokens: deterministic allow/deny.

Exit 0 = allow, exit 2 = block (stderr is shown to Claude as the reason).
Usage: guard.py bash|file   (hook payload JSON on stdin)
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))

SECRET_PATH = re.compile(
    r"(^|[\s/'\"=<])("
    r"\.env(\.[\w-]+)?"            # .env, .env.local, .env.prod
    r"|deploy/envs/[\w.-]+\.env"   # deploy/envs/staging.env
    r"|[\w.-]+\.pem|[\w.-]+\.p12|[\w.-]+\.jks|id_(rsa|ed25519|ecdsa)(\.pub)?"
    r"|\.npmrc|\.pgpass|credentials(\.json)?"
    r")(?=$|[\s'\";|&)])"
)
SECRET_ALLOW = re.compile(r"(\.env\.example|example\.env|\.env\.sample|id_\w+\.pub)$")


_CTX = {}

# Quality gates the agent must not weaken (idea from ECC config-protection). Humans edit them in a
# session started with DK_ALLOW_QUALITY_EDIT=1 — the agent cannot set that variable itself.
QUALITY_FILES = re.compile(
    r"(^|/)(eslint\.config\.[cm]?[jt]s|\.eslintrc(\.\w+)?|\.prettierrc(\.\w+)?|prettier\.config\.[cm]?js"
    r"|tsconfig(\.\w+)?\.json|spotbugs-exclude\.xml|[\w-]*pmd[\w-]*\.xml|\.gitleaks\.toml|\.semgrepignore"
    r"|\.semgrep\.ya?ml|ArchitectureTest\.java|ac-trace\.py|check-migrations\.sh)$"
    r"|(^|/)\.github/workflows/[^/]+\.ya?ml$")
SUPPRESSIONS = {
    "@Disabled": r"@Disabled\b", "@Ignore": r"@Ignore\b", "@SuppressFBWarnings": r"@SuppressFBWarnings\b",
    "NOPMD": r"\bNOPMD\b", "CHECKSTYLE:OFF": r"CHECKSTYLE:OFF", "eslint-disable": r"eslint-disable",
    "@ts-ignore": r"@ts-ignore", "@ts-nocheck": r"@ts-nocheck", "@ts-expect-error": r"@ts-expect-error",
    "nosemgrep": r"nosemgrep", "gitleaks:allow": r"gitleaks:allow",
    ".skip/.only": r"\b(?:it|test|describe)\.(?:skip|only)\(|\bx(?:it|describe)\(",
}
POM_WEAKEN = {
    "skipTests": r"skipTests|maven\.test\.skip|<skip>\s*true", "testFailureIgnore": r"testFailureIgnore",
    "failOn*=false": r"<fail\w*>\s*false", "haltOnFailure": r"haltOnFailure>\s*false",
}


def block(msg: str, rule: str = "other") -> None:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from dk_event import emit, project_root
        emit(project_root(_CTX.get("cwd")), {"ev": "blocked", "rule": rule, "tool": _CTX.get("tool")})
    except Exception:
        pass
    print(f"[dk guard] {msg}", file=sys.stderr)
    sys.exit(2)


def project_dir(payload: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())


def is_secret(path_text: str) -> bool:
    for m in SECRET_PATH.finditer(path_text):
        token = m.group(2)
        if not SECRET_ALLOW.search(token):
            return True
    return False


def prod_hosts(root: Path) -> set[str]:
    hosts = set()
    envs = root / "deploy" / "envs"
    if envs.is_dir():
        for f in envs.glob("prod*.env"):
            for line in f.read_text(errors="ignore").splitlines():
                m = re.match(r"\s*(DEPLOY_HOST|DB_HOST|PUBLIC_URL)\s*=\s*(\S+)", line)
                if m:
                    v = re.sub(r"^https?://", "", m.group(2)).split("/")[0].split(":")[0]
                    v = v.split("@")[-1]
                    if v:
                        hosts.add(v)
    return hosts


def push_dir(flat: str, root: Path) -> Path:
    """Directory the push actually runs in: `git -C <dir>` or the last `cd <dir>` before it."""
    before = flat.partition("git push")[0]
    m = re.search(r"git\s+-C\s+(\S+)\s*$", before.rstrip())
    target = m.group(1) if m else None
    if target is None:
        cds = re.findall(r"(?:^|[;&|]\s*)cd\s+(\S+)", before)
        target = cds[-1] if cds else None
    if not target:
        return root
    p = Path(os.path.expanduser(target.strip("'\"")))
    p = p if p.is_absolute() else root / p
    return p if p.is_dir() else root


HEREDOC = re.compile(r"(?P<head>[^\n]*)<<-?\s*(['\"]?)(?P<tag>\w+)\2[^\n]*\n.*?\n\s*(?P=tag)\s*(?=\n|$)", re.S)
TEXT_ARG = re.compile(r"""(?P<lead>(?:\s(?:-m|--message|--body|--title|--notes|--subject|-t|-b)(?:=|\s+)|\b(?:echo|printf)\s+(?:-\w+\s+)*))"""
                      r"""(?P<q>'[^']*'|"(?:[^"\\]|\\.)*")""")
SHELLS = re.compile(r"\b(?:bash|sh|zsh|ssh|python3?|node|eval)\b")


def code_only(cmd: str) -> str:
    """The command with *text* blanked — heredoc bodies fed to non-shell commands and quoted arguments of
    message flags (-m, --body, --title…) or echo/printf — so a commit message or PR body that merely
    mentions `git push` / `gh pr merge` is not mistaken for running it (known false positive; idea from
    ECC's shell-segment parsing). Code passed to a shell (bash -c, heredoc into bash/ssh) is kept, and
    secrets/prod hosts are still checked on the full text."""
    s = HEREDOC.sub(lambda m: m.group(0) if SHELLS.search(m.group("head")) else m.group("head") + "<<TEXT", cmd)
    s = TEXT_ARG.sub(lambda m: m.group("lead") + "''", s)
    return " ".join(s.split())


def shell_write_targets(cmd: str) -> list:
    """Paths a shell command may write: redirection targets, sed -i files, tee args, cp/mv/install destination."""
    out = re.findall(r">>?\s*['\"]?([^\s;&|'\"]+)", cmd)
    for seg in re.split(r"\|\||&&|[;|\n]", cmd):
        try:
            words = shlex.split(seg)
        except ValueError:
            words = seg.split()
        while words and re.fullmatch(r"\w+=\S*|sudo|env|command", words[0]):
            words = words[1:]
        if not words:
            continue
        name, args = Path(words[0]).name, [w for w in words[1:]]
        files = [w for w in args if not w.startswith("-")]
        if name == "sed" and any(w.startswith("-i") or w == "--in-place" for w in args):
            out += files[1:] if not any(w in ("-e", "-f") for w in args) else files
        elif name == "tee":
            out += files
        elif name in ("cp", "mv", "install", "ln", "truncate", "rm") and files:
            out += files if name in ("truncate", "rm") else files[-1:]
    return out


def check_bash(cmd: str, root: Path) -> None:
    full = " ".join(cmd.split())
    flat = code_only(cmd)

    # 0. Shell writes to quality configs (sed -i, redirection, tee, cp/mv onto them) — same rule as the file tools.
    if (root / ".dk" / "state.md").exists() and os.environ.get("DK_ALLOW_QUALITY_EDIT") != "1":
        for target in shell_write_targets(cmd):
            target = target.replace("\\", "/")
            if target.startswith("./"):
                target = target[2:]
            if QUALITY_FILES.search(target) and (root / target).exists():
                block(f"Lệnh shell sửa {target} — cấu hình kiểm tra chất lượng, agent không được nới. Sửa code; "
                      "cần đổi luật thì nhờ người (DK_ALLOW_QUALITY_EDIT=1).", "quality_config")

    # 1. Secrets never enter the model's context.
    if is_secret(full):
        block("Lệnh chạm vào file bí mật (.env, deploy/envs/*.env, khóa). Dùng file *.example, "
              "hoặc để script deploy/dk-check tự đọc. Nếu thật sự cần, người dùng tự chạy lệnh.", "secret_read")

    # 2. Production is human-only.
    if re.search(r"deploy\.sh\s+['\"]?prod", flat) or re.search(
            r"(--context|--env|-e|ENV=|SPRING_PROFILES_ACTIVE=)\s*=?\s*['\"]?prod(uction)?\b", flat):
        block("Triển khai/ thao tác production chỉ do người thực hiện. Agent chỉ làm trên non-prod.", "prod")
    for h in prod_hosts(root):
        if h and h in full:
            block(f"Lệnh trỏ tới host production ({h}). Agent chỉ làm trên non-prod.", "prod_host")

    # 3. Human gates.
    if re.search(r"\bgh\s+pr\s+merge\b", flat):
        block("Merge vào main là cổng duyệt của người. Hãy để người dùng merge PR.", "merge")
    if re.search(r"dk-state\.sh\s+approve\b", flat):
        block("Phê duyệt cổng (spec/contract) chỉ do người chạy bằng /dk:approve.", "approve")
    if re.search(r"\bgit\s+push\b", flat):
        if re.search(r"\s(--force(?!-with-lease)|-f)\b", flat):
            block("Không force-push. Dùng --force-with-lease trên nhánh feature nếu thật cần.", "force_push")
        push_args = [a.strip("'\"") for a in re.split(r"[;&|]", flat.split("git push", 1)[1])[0].split()]
        if any(re.fullmatch(r"(\+?[\w/.-]*:)?(refs/heads/)?(main|master)", a) for a in push_args):
            block("Không push thẳng lên main. Mở PR qua /dk:review.", "push_main")
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=push_dir(flat, root),
                                capture_output=True, text=True).stdout.strip()
        if branch in ("main", "master") and not re.search(r"--tags|\stag\b", flat):
            block("Đang ở main. Tạo nhánh feature rồi push nhánh đó.", "push_from_main")
    if re.search(r"\bgit\s+commit\b.*--no-verify", flat):
        block("Không bỏ qua kiểm tra khi commit.", "no_verify")
    if re.search(r"\brm\s+(-\w*r\w*f|-\w*f\w*r)\w*\s+(/|~|\$HOME|\.\.)(\s|$|/\s|/\*)", flat):
        block("Lệnh rm -rf nhắm vào thư mục gốc/ home/ thư mục cha bị chặn.", "rm_rf")

    # 4. Pre-commit gate (deterministic checks, no tokens).
    if re.search(r"\bgit\s+commit\b", flat) and (root / ".dk").is_dir():
        mode = "precommit-strict" if os.environ.get("CLAUDE_PLUGIN_OPTION_STRICT_GATES", "true") != "false" else "precommit"
        r = subprocess.run([shutil.which("bash"), str(PLUGIN_ROOT / "scripts" / "dk-check.sh"), mode], cwd=root,
                           capture_output=True, text=True)
        if r.returncode != 0:
            tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-25:])
            block("Pre-commit checks FAILED — sửa rồi commit lại:\n" + tail, "precommit_failed")


def check_file(tool: str, inp: dict, root: Path) -> None:
    path = inp.get("file_path") or inp.get("notebook_path") or ""
    if not path:
        return
    p = Path(path)
    rel = str(p.resolve().relative_to(root.resolve())) if p.is_absolute() and str(p.resolve()).startswith(str(root.resolve())) else path
    if is_secret(" " + rel):
        block(f"{rel} là file bí mật — agent không đọc/ghi. Cập nhật deploy/.env.example thay vào đó.", "secret_file")
    if tool != "Read":
        if rel.replace("\\", "/").endswith(".dk/state.md"):
            block(".dk/state.md chỉ được sửa qua scripts/dk-state.sh.", "state_edit")
        if "/db/migration/" in rel.replace("\\", "/") and p.exists():
            tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(p)], cwd=root,
                                     capture_output=True).returncode == 0
            if tracked:
                block(f"{rel} đã commit — không sửa migration cũ. Tạo file V<yyyyMMddHHmm>__*.sql mới.", "migration_edit")
        check_quality(tool, inp, rel.replace("\\", "/"), p, root)


def _new_and_old(tool: str, inp: dict, p: Path):
    """Text the edit adds and the text it replaces (whole file for Write)."""
    if tool == "Edit":
        return inp.get("new_string") or "", inp.get("old_string") or ""
    if tool == "MultiEdit":
        edits = inp.get("edits") or []
        return "\n".join(e.get("new_string") or "" for e in edits), "\n".join(e.get("old_string") or "" for e in edits)
    if tool == "Write":
        try:
            old = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
        except OSError:
            old = ""
        return inp.get("content") or "", old
    return "", ""


def check_quality(tool: str, inp: dict, rel: str, p: Path, root: Path) -> None:
    """Agents must fix code, not weaken the checks (ECC config-protection, adapted to dk)."""
    if os.environ.get("DK_ALLOW_QUALITY_EDIT") == "1" or not (root / ".dk" / "state.md").exists():
        return
    if QUALITY_FILES.search(rel) and p.exists():
        block(f"{rel} là cấu hình kiểm tra chất lượng — agent không sửa để cho qua. Sửa code; nếu thật sự cần đổi "
              "luật, dừng lại và nhờ người (người mở phiên với DK_ALLOW_QUALITY_EDIT=1).", "quality_config")
    new, old = _new_and_old(tool, inp, p)
    if not new:
        return
    added = [name for name, rx in SUPPRESSIONS.items() if len(re.findall(rx, new)) > len(re.findall(rx, old))]
    if added and not rel.endswith((".md", ".txt")):
        block(f"Không thêm {', '.join(added)} vào {rel} để né kiểm tra/test. Sửa nguyên nhân; nếu là báo nhầm, "
              "ghi lý do vào PR và nhờ người thêm.", "suppression")
    if rel.endswith("pom.xml"):
        weak = [name for name, rx in POM_WEAKEN.items() if len(re.findall(rx, new)) > len(re.findall(rx, old))]
        mins_old, mins_new = re.findall(r"<minimum>\s*([\d.]+)", old), re.findall(r"<minimum>\s*([\d.]+)", new)
        if mins_new and mins_old and min(map(float, mins_new)) < min(map(float, mins_old)):
            weak.append("hạ <minimum> coverage")
        if weak:
            block(f"pom.xml: không {', '.join(weak)} — cổng chất lượng chỉ người được nới.", "quality_config")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "bash"
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # never break the session on a malformed payload
    root = project_dir(payload)
    inp = payload.get("tool_input") or {}
    _CTX.update(cwd=str(root), tool=payload.get("tool_name") or mode)
    if mode == "bash":
        check_bash(inp.get("command", ""), root)
    else:
        check_file(payload.get("tool_name", ""), inp, root)
    sys.exit(0)


if __name__ == "__main__":
    main()
