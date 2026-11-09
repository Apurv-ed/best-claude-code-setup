#!/bin/bash
# PreToolUse (Write|Edit|MultiEdit|NotebookEdit): ask before editing an EXISTING linter, formatter
# or type-check config file (fix the code, not the config). Decider: scripts/config_protection.py.
# Fails silent: any problem means no output and exit 0, never a blocked tool call.
. "$(dirname "$0")/lib-python.sh"
[ -n "$PYTHON" ] || exit 0
S="$(dirname "$0")/../scripts/config_protection.py"
[ -r "$S" ] || exit 0
"$PYTHON" "$S" 2>/dev/null
exit 0
