#!/usr/bin/env python3
"""PreToolUse guard for the dk plugin. Zero tokens: deterministic allow/deny.

Exit 0 = allow, exit 2 = block (stderr is shown to Claude as the reason).
Usage: guard.py bash|file   (hook payload JSON on stdin)
"""
import json
import os
import re
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


def check_bash(cmd: str, root: Path) -> None:
    flat = " ".join(cmd.split())

    # 1. Secrets never enter the model's context.
    if is_secret(flat):
        block("Lệnh chạm vào file bí mật (.env, deploy/envs/*.env, khóa). Dùng file *.example, "
              "hoặc để script deploy/dk-check tự đọc. Nếu thật sự cần, người dùng tự chạy lệnh.", "secret_read")

    # 2. Production is human-only.
    if re.search(r"deploy\.sh\s+['\"]?prod", flat) or re.search(
            r"(--context|--env|-e|ENV=|SPRING_PROFILES_ACTIVE=)\s*=?\s*['\"]?prod(uction)?\b", flat):
        block("Triển khai/ thao tác production chỉ do người thực hiện. Agent chỉ làm trên non-prod.", "prod")
    for h in prod_hosts(root):
        if h and h in flat:
            block(f"Lệnh trỏ tới host production ({h}). Agent chỉ làm trên non-prod.", "prod_host")

    # 3. Human gates.
    if re.search(r"\bgh\s+pr\s+merge\b", flat):
        block("Merge vào main là cổng duyệt của người. Hãy để người dùng merge PR.", "merge")
    if re.search(r"dk-state\.sh\s+approve\b", flat):
        block("Phê duyệt cổng (spec/contract) chỉ do người chạy bằng /dk:approve.", "approve")
    if re.search(r"\bgit\s+push\b", flat):
        if re.search(r"\s(--force(?!-with-lease)|-f)\b", flat):
            block("Không force-push. Dùng --force-with-lease trên nhánh feature nếu thật cần.", "force_push")
        push_args = re.split(r"[;&|]", flat.split("git push", 1)[1])[0].split()
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
                block(f"{rel} đã commit — không sửa migration cũ. Tạo file V<next>__*.sql mới.", "migration_edit")


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
