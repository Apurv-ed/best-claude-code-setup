#!/bin/bash
# Stop hook: require a self-review pass only when code was written or edited
# since the last real user prompt. Pure Q&A turns stop silently (zero cost).
# Hook input arrives as JSON on stdin; the transcript at transcript_path is JSONL.
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 -c '
import json, sys

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

if d.get("stop_hook_active"):
    sys.exit(0)

path = d.get("transcript_path") or ""
EDIT_TOOLS = ("Write", "Edit", "NotebookEdit")
edited = False
try:
    with open(path) as f:
        for line in f:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            message = entry.get("message") or {}
            content = message.get("content")
            if entry.get("type") == "user":
                # A genuine user prompt (string content, or blocks with no
                # tool_result) resets the flag; tool results do not.
                if isinstance(content, str):
                    edited = False
                elif isinstance(content, list) and not any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content
                ):
                    edited = False
                continue
            if not isinstance(content, list):
                continue
            if any(
                isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in EDIT_TOOLS
                for b in content
            ):
                edited = True
except Exception:
    sys.exit(0)

if edited:
    reason = (
        "Code was written or modified this turn. Before stopping, complete the 3-pass self-review: "
        "(1) Verification: run the relevant tests/checks and confirm they pass. "
        "(2) Adversarial review: which assumptions did you not verify? How could this fail? "
        "(3) Completeness: re-read the original request - was everything done? "
        "Fix any issues found, then stop."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
'
