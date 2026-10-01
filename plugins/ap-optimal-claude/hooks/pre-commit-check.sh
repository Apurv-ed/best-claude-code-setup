#!/bin/bash
# PreToolUse hook (git commit): show staged files + git status to the model.
# Plain stdout from a PreToolUse hook does NOT reach the model - it must be
# JSON with hookSpecificOutput.additionalContext.
git rev-parse --git-dir > /dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 -c '
import json, subprocess

def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""

staged = run(["git", "diff", "--staged", "--name-only"])
status = run(["git", "status", "--short"])
ctx = "=== Staged files ===\n" + staged + "\n\n=== Git status ===\n" + status
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx}}))
'
