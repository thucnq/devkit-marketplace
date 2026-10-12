#!/usr/bin/env python3
"""Hook entry point: records what happened in a dk project, at zero model tokens.

Usage (from hooks.json): dk-log.py prompt|tool|tool_fail|subagent|turn|end   (payload on stdin)
Records: which /dk command ran, tool calls (truncated, redacted), failures, subagent verdicts,
token usage per turn (from the transcript), session end. Prompts themselves are NOT stored.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dk_event import emit, project_root, redact  # noqa: E402

CMD_RE = re.compile(r"<command-name>/?([\w:-]+)</command-name>")
# Phrases that often mean the work was cut short (idea from ECC delivery-gate). Logged as keys only, never text.
EXCUSES = {
    "pre-existing": r"pre-?existing|lỗi có sẵn|lỗi cũ|đã đỏ từ trước",
    "flaky": r"\bflaky\b|chập chờn|lúc được lúc không",
    "unrelated": r"unrelated to (?:this|my|the) change|không liên quan (?:tới|đến) thay đổi",
    "skip-tests": r"skip(?:ping|ped)? (?:the )?tests?|bỏ qua test|tắt test|chưa chạy test",
    "later": r"\bfor now\b|\bleave (?:it|this) for later\b|để sau|làm sau|tạm bỏ",
}
COMPACT_AT = int(os.environ.get("DK_COMPACT_AT", "120000"))   # context tokens before suggesting /compact
COMPACT_STEP = 40000


def session_file(root, sid):
    d = root / ".dk" / "log" / ".sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{sid}.json"


def load_session(root, sid):
    try:
        return json.loads(session_file(root, sid).read_text())
    except Exception:
        return {"offset": 0, "seen": [], "cmd": None}


def save_session(root, sid, s):
    s["seen"] = s["seen"][-500:]
    try:
        session_file(root, sid).write_text(json.dumps(s))
    except Exception:
        pass


def usage_since(path, state):
    """Sum token usage of assistant messages appended to the transcript since the last call."""
    totals, cmd = {}, None
    try:
        with open(path, "rb") as fh:
            fh.seek(state.get("offset", 0))
            data = fh.read()
            # only consume complete lines; the transcript is written asynchronously
            end = data.rfind(b"\n") + 1
            state["offset"] = state.get("offset", 0) + end
    except OSError:
        return totals, cmd
    seen = set(state.get("seen", []))
    state["last_text"] = ""
    for raw in data[:end].splitlines():
        try:
            d = json.loads(raw)
        except Exception:
            continue
        msg = d.get("message") or {}
        if d.get("type") == "user" and isinstance(msg.get("content"), str):
            m = CMD_RE.search(msg["content"])
            if m:
                cmd = m.group(1)
        if d.get("type") != "assistant" or not msg.get("usage"):
            continue
        mid = msg.get("id") or d.get("uuid")
        if mid in seen:
            continue
        seen.add(mid)
        state.setdefault("seen", []).append(mid)
        u, model = msg["usage"], msg.get("model", "unknown")
        if not d.get("isSidechain"):
            state["ctx"] = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                            + u.get("cache_creation_input_tokens", 0))
            texts = [c.get("text", "") for c in msg.get("content") or [] if isinstance(c, dict) and c.get("type") == "text"]
            if texts:
                state["last_text"] = "\n".join(texts)[-4000:]
        t = totals.setdefault(model, {"in": 0, "cache_read": 0, "cache_write": 0, "out": 0, "calls": 0})
        t["in"] += u.get("input_tokens", 0)
        t["cache_read"] += u.get("cache_read_input_tokens", 0)
        t["cache_write"] += u.get("cache_creation_input_tokens", 0)
        t["out"] += u.get("output_tokens", 0)
        t["calls"] += 1
    return totals, cmd


def tool_target(name, inp):
    if name == "Bash":
        return redact(inp.get("command", ""), 120)
    if name in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        p = inp.get("file_path") or inp.get("notebook_path") or ""
        root = os.environ.get("CLAUDE_PROJECT_DIR") or ""
        return p[len(root):].lstrip("/") if root and p.startswith(root) else p
    if name in ("Agent", "Task"):
        return inp.get("subagent_type") or "general-purpose"
    if name in ("Grep", "Glob"):
        return redact(inp.get("pattern", ""), 60)
    if name == "Skill":
        return inp.get("skill")
    return None


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        p = json.load(sys.stdin)
    except Exception:
        return
    root = project_root(p.get("cwd"))
    if root is None:
        return
    sid = (p.get("session_id") or "nosession")[:12]
    s = load_session(root, sid)
    base = {"sid": sid, "cmd": s.get("cmd"), "agent": p.get("agent_type")}

    if kind == "prompt":
        text = (p.get("prompt") or "").strip()
        m = re.match(r"/(dk:[\w-]+)", text)
        if m:
            s["cmd"] = m.group(1)
            emit(root, {**base, "ev": "command", "cmd": s["cmd"], "args_chars": max(len(text) - len(m.group(0)), 0)})
        else:
            emit(root, {**base, "ev": "prompt", "chars": len(text)})  # human steering, counted not stored
    elif kind == "tool":
        name = p.get("tool_name")
        inp = p.get("tool_input") or {}
        emit(root, {**base, "ev": "tool", "tool": name, "target": tool_target(name, inp)})
    elif kind == "tool_fail":
        name = p.get("tool_name")
        emit(root, {**base, "ev": "tool_fail", "tool": name,
                    "target": tool_target(name, p.get("tool_input") or {}),
                    "error": redact(p.get("tool_error") or p.get("error") or "", 240)})
    elif kind == "subagent":
        last = p.get("last_assistant_message") or ""
        verdict = re.search(r"VERDICT:\s*(APPROVE|CHANGES_REQUIRED)", last)
        sub = {"offset": 0, "seen": []}
        usage, _ = usage_since(p.get("agent_transcript_path") or "", sub) if p.get("agent_transcript_path") else ({}, None)
        emit(root, {**base, "ev": "subagent", "agent": p.get("agent_type"),
                    "verdict": verdict.group(1) if verdict else None,
                    "blockers": len(re.findall(r"^- \[", last.split("## Should fix")[0], re.M)) if verdict else None,
                    "usage": usage or None})
    elif kind in ("turn", "end"):
        usage, cmd = usage_since(p.get("transcript_path") or "", s)
        if cmd and cmd.startswith("dk:"):
            s["cmd"] = cmd
        if usage:
            emit(root, {**base, "ev": "usage", "cmd": s.get("cmd"), "usage": usage})
        notices = []
        text = p.get("last_assistant_message") or s.pop("last_text", "") or ""
        hits = [k for k, rx in EXCUSES.items() if re.search(rx, text, re.I)] if kind == "turn" else []
        if hits:
            emit(root, {**base, "ev": "excuse", "keys": hits})
            notices.append(f"⚠ dk: câu trả lời vừa rồi có dấu hiệu bỏ dở ({', '.join(hits)}) — kiểm lại trước khi chấp nhận.")
        ctx = s.get("ctx", 0)
        if ctx < s.get("ctx_warned", 0) - COMPACT_STEP:  # compacted or cleared since the last notice
            s["ctx_warned"] = 0
        if kind == "turn" and ctx >= COMPACT_AT and ctx >= s.get("ctx_warned", 0) + COMPACT_STEP:
            s["ctx_warned"] = ctx
            emit(root, {**base, "ev": "context_high", "tokens": ctx})
            notices.append(f"ℹ dk: ngữ cảnh ~{ctx // 1000}k token. Trạng thái đã nằm trong file (.dk/, docs/) — "
                           "xong bước hiện tại thì /compact hoặc /clear để đỡ tốn token.")
        if notices:
            print(json.dumps({"systemMessage": " ".join(notices)}, ensure_ascii=False))
        if kind == "end":
            emit(root, {**base, "ev": "session_end", "reason": p.get("reason")})
            try:
                session_file(root, sid).unlink()
            except OSError:
                pass
            return
    save_session(root, sid, s)


if __name__ == "__main__":
    main()
