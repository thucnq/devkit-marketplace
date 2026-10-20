#!/usr/bin/env python3
"""Append-only project event log for later retrospectives (.dk/log/<author>.jsonl).

One file per author so three people never conflict when merging. Never stores prompts,
file contents or secrets: commands are truncated and redacted.

Library: emit(root, {"ev": ...})            CLI: dk_event.py <ev> [key=value ...]
                                                  dk_event.py note   (note text on stdin)
                                                  dk_event.py lessons [N]   last N notes tagged #lesson (all authors)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REDACT = re.compile(
    r"(?i)((?:password|passwd|secret|token|api[_-]?key|authorization)\s*[=:]\s*|bearer\s+)\S+"
    r"|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|-----BEGIN[^-]+-----")


def project_root(start=None):
    p = Path(start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    for d in [p, *p.parents]:
        if (d / ".dk").is_dir():
            return d
    return None


def redact(text, limit=160):
    text = " ".join(str(text).split())
    text = REDACT.sub(lambda m: (m.group(1) or "") + "***", text)
    return text[:limit] + ("…" if len(text) > limit else "")


def _git(root, *args):
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return ""


def _author(root):
    email = _git(root, "config", "user.email") or os.environ.get("USER", "unknown")
    return re.sub(r"[^a-z0-9_-]", "-", email.split("@")[0].lower()) or "unknown"


def _state(root, key):
    f = root / ".dk" / "state.md"
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(key + ":"):
                return line.split(":", 1)[1].strip()
    return None


def emit(root, event):
    if root is None:
        return
    try:
        log_dir = root / ".dk" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "phase": _state(root, "phase"), "feature": _state(root, "feature"),
               "branch": _git(root, "branch", "--show-current") or None}
        rec.update({k: v for k, v in event.items() if v is not None})
        with open(log_dir / f"{_author(root)}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging must never break the workflow


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ev = sys.argv[1]
    if ev == "lessons":
        root = project_root()
        if root is None:
            return
        found = []
        for f in (root / ".dk" / "log").glob("*.jsonl"):
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                if '"lesson"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("ev") == "note" and "lesson" in (e.get("tags") or []):
                    found.append((e.get("ts", ""), re.sub(r"\s*#lesson\b", "", e.get("text", "")).strip()))
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        for ts, text in sorted(found)[-n:]:
            print(f"- {ts[:10]} {text[:200]}")
        return
    data = {"ev": ev}
    for kv in sys.argv[2:]:
        k, _, v = kv.partition("=")
        data[k] = v
    if ev == "note":
        text = sys.stdin.read().strip()
        if not text:
            print("Ghi chú trống - dùng: /dk:note #tag nội dung")
            return
        data["tags"] = re.findall(r"#([\w-]+)", text) or ["general"]
        data["text"] = redact(text, 2000)
    root = project_root()
    if root is None:
        print("Không tìm thấy thư mục .dk - chạy trong một dự án dk.")
        return
    emit(root, data)
    if ev == "note":
        print(f"📝 Đã ghi chú ({', '.join('#' + t for t in data['tags'])}).")


if __name__ == "__main__":
    main()
