#!/bin/bash
# PreToolUse (Bash|Write|Edit|MultiEdit|NotebookEdit): folder guard and delete/write guard.
# Decider: scripts/safety_guard.py (ADR-0105). Silent unless it decides something.
# Fails silent: any problem means no output and exit 0, never a blocked tool call.
. "$(dirname "$0")/lib-python.sh"
[ -n "$PYTHON" ] || exit 0
S="$(dirname "$0")/../scripts/safety_guard.py"
[ -r "$S" ] || exit 0
# Not exec: a broken Python can exit 1 or 2, and exit 2 on PreToolUse would block every command.
"$PYTHON" "$S" 2>/dev/null
exit 0
