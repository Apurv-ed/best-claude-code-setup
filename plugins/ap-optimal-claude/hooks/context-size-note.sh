#!/bin/bash
# UserPromptSubmit hook: once per session, a measured note when the context window passes
# 40% (the number comes from Claude Code via the status line; see scripts/context_meter.py).
# States a measurement, fires at most once per session, fails silent.
# Canary: python3 scripts/test_context_meter.py --live
PYTHON=$(command -v python3 || command -v python) 2>/dev/null
[ -n "$PYTHON" ] || exit 0
"$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/context_meter.py" hook 2>/dev/null || true
exit 0
