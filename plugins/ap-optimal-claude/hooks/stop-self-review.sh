#!/bin/bash
# Stop hook: nudge once when code was edited this turn and no command ran after the last edit.
# Speaks only if a non-.md/.txt file was changed (Write/Edit/NotebookEdit) and no
# Bash/PowerShell/Agent call came after it. Output is non-blocking feedback
# (hookSpecificOutput.additionalContext). Fails silent. Text: Anthropic Sonnet 5.5 guide,
# "Verification on coding tasks". Hook input is JSON on stdin; transcript_path is JSONL.
. "$(dirname "$0")/lib-python.sh"
[ -n "$PYTHON" ] || exit 0
exec "$PYTHON" -c '
import json, sys

try:
    d = json.load(sys.stdin)
    if d.get("stop_hook_active"):
        sys.exit(0)
    EDIT = ("Write", "Edit", "NotebookEdit")
    RUN = ("Bash", "PowerShell", "Agent", "Task")
    DOCS = (".md", ".txt")
    pending = False  # a code edit with no command after it, this turn
    with open(d.get("transcript_path") or "", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if not isinstance(e, dict):
                continue
            m = e.get("message")
            c = m.get("content") if isinstance(m, dict) else None
            if e.get("type") == "user":
                # A genuine user prompt resets the flag; tool results do not.
                if isinstance(c, str) or (isinstance(c, list) and not any(
                        isinstance(b, dict) and b.get("type") == "tool_result" for b in c)):
                    pending = False
                continue
            for b in c if isinstance(c, list) else []:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                inp = b.get("input") or {}
                p = str(inp.get("file_path") or inp.get("notebook_path") or "")
                if b.get("name") in EDIT and not p.lower().endswith(DOCS):
                    pending = True
                elif b.get("name") in RUN:
                    pending = False
    if pending:
        msg = ("When you change code that can be run, built, or type-checked, run a real check that exercises the change before reporting it done: the project\047s tests, type-checker, or build, or the changed command itself. A syntax-only check, or a check command that failed to start, does not count; if all that is missing is the project\047s declared dependencies, install them with its own package manager and lockfile (e.g. npm install, pip install -r requirements.txt), never via sudo or the system package manager, unless told not to. Only if no real check can run here, say which one you did not run and why instead of reporting the change as done.")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": msg}}))
except SystemExit:
    raise
except Exception:
    sys.exit(0)
'
