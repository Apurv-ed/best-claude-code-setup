#!/bin/bash
# PreToolUse hook (git commit): show staged files + git status to the model.
# Plain stdout from a PreToolUse hook does NOT reach the model - it must be
# JSON with hookSpecificOutput.additionalContext.
# hooks.json narrows this with "if": "Bash(git commit*)", but Claude Code runs the
# hook anyway when it cannot parse a command (loops, $(), heredocs), so the script
# checks the command itself and stays silent unless it really commits.
git rev-parse --git-dir > /dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 -c '
import json, re, subprocess, sys

try:
    cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
except Exception:
    sys.exit(0)
if not re.search(r"\bgit(\s+-[cC]\s+\S+)*\s+commit\b", cmd):
    sys.exit(0)

def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""

MAX = 40
def cap(text):
    lines = text.splitlines()
    return "\n".join(lines[:MAX] + ([f"... {len(lines) - MAX} more"] if len(lines) > MAX else []))

ctx = "=== Staged files ===\n" + cap(run(["git", "diff", "--staged", "--name-only"])) + \
      "\n\n=== Git status ===\n" + cap(run(["git", "status", "--short"]))
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx}}))
'
