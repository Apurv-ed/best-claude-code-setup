#!/usr/bin/env python3
"""Context meter: one measured note per session when the context window passes 40%.

No hook input carries the context size; only the status line gets it from Claude Code
(context_window.used_percentage and context_window_size, code.claude.com/docs/en/statusline).
So this script has two modes:

  statusline <command>  Wraps the real status bar: saves the window numbers for this session,
                        then runs <command> with the same input and shows its output. Always
                        exits 0 so the status bar never breaks.
  hook                  UserPromptSubmit: the first time the saved number is 40% or more,
                        shows the user one line and tells Claude to suggest "end session"
                        then /clear once. Silent on any problem.

Data: <claude dir>/context-meter/<session>.json (a few bytes each, older than 7 days removed).
/clear starts a new session id, so the note can fire again in the fresh conversation.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

THRESHOLD = 40
KEEP_DAYS = 7


def data_dir() -> Path:
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return claude / "context-meter"


def safe_id(session_id) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", str(session_id or ""))[:100]


def record(raw: bytes) -> None:
    d = json.loads(raw.decode("utf-8"))
    sid = safe_id(d.get("session_id"))
    cw = d.get("context_window") or {}
    pct = cw.get("used_percentage")
    if not sid or not isinstance(pct, (int, float)):
        return
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{sid}.json").write_text(json.dumps(
        {"used_percentage": pct, "context_window_size": cw.get("context_window_size"), "time": int(time.time())}))
    cutoff = time.time() - KEEP_DAYS * 86400
    for p in folder.iterdir():
        if p.stat().st_mtime < cutoff:
            p.unlink()


def statusline(command: str) -> int:
    raw = sys.stdin.buffer.read()
    try:
        record(raw)
    except Exception:
        pass
    try:
        out = subprocess.run(command, shell=True, input=raw, stdout=subprocess.PIPE).stdout
        sys.stdout.buffer.write(out)
    except Exception:
        pass
    return 0


def hook() -> int:
    try:
        sid = safe_id(json.loads(sys.stdin.read()).get("session_id"))
        if not sid:
            return 0
        folder = data_dir()
        marker = folder / f"{sid}.noted"
        if marker.exists():
            return 0
        d = json.loads((folder / f"{sid}.json").read_text())
        pct = d["used_percentage"]
        if pct < THRESHOLD:
            return 0
        marker.write_text("1")
        size = d.get("context_window_size")
        window = f"{size // 1000}K-token window" if isinstance(size, int) else "context window"
        print(json.dumps({
            "systemMessage": f"This conversation is {pct:.0f}% full. For the best quality, type end session, then /clear to start fresh.",
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": (
                    f"MEASURED: this conversation fills {pct:.0f}% of its {window} (reported by Claude Code). "
                    "Answer the user's message first, then add one line suggesting they type 'end session' "
                    "and then /clear for the best quality. Say it once; do not repeat it later in this session."),
            },
        }))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "statusline":
        sys.exit(statusline(sys.argv[2]))
    if len(sys.argv) >= 2 and sys.argv[1] == "hook":
        sys.exit(hook())
    sys.exit(0)
