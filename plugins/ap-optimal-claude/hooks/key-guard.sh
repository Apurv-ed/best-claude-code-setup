#!/bin/bash
# PreToolUse (Write|Edit|MultiEdit|NotebookEdit): deny writing an API key, token or password
# into a file; warn on a broad generic key pattern. Scanner: scripts/key_guard.py.
# Fails silent: any problem means no output and exit 0, never a blocked tool call.
. "$(dirname "$0")/lib-python.sh"
[ -n "$PYTHON" ] || exit 0
S="$(dirname "$0")/../scripts/key_guard.py"
[ -r "$S" ] || exit 0
# Not exec: a broken Python or unreadable script can exit 1 or 2, and exit 2 on PreToolUse
# would block every write. Lines over 4,000 characters are skipped, so a scan stays far
# under the 10 s hook timeout and no orphan is left behind.
"$PYTHON" "$S" 2>/dev/null
exit 0
