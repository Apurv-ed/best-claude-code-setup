#!/bin/bash
# UserPromptSubmit hook: nudge (never block) when the transcript shows a
# correction-shaped moment - an interruption or a denied/failed tool call -
# with no memory file written since. Fires at most once per session.
#
# Why this exists
# ----------------
# tasks/lessons.md was mandated everywhere and only exists in 20 of ~50
# project dirs - the "log this after a correction" instruction gets skipped
# under context pressure. Auto Memory (code.claude.com/docs/en/memory) is
# the replacement store, but writing to it after a correction is just as
# skippable an instruction unless nudged. This hook states a fact - "a
# correction-shaped signal occurred and no memory write followed it" - and
# never asserts that a correction definitely happened, because that would be
# a judgment call this hook has no business making.
#
# Design note: this was originally scoped as a Stop hook. Verified against
# the hooks reference that Stop does not support non-blocking
# hookSpecificOutput.additionalContext (only block/continue) - UserPromptSubmit
# does, so the check runs there instead, looking back at the transcript
# accumulated so far rather than forward from Stop.
#
# Fragility, stated plainly
# --------------------------
# Correction detection is a heuristic (an interruption marker or an is_error
# tool_result), not a semantic judgment - it can both miss real corrections
# (a plain retyped correction with no interruption/denial) and flag
# false positives (an incidental permission denial unrelated to any lesson).
# That is why this hook nudges instead of blocking: false positives cost a
# skippable one-line note, never a stalled turn.
command -v python3 >/dev/null 2>&1 || exit 0

INPUT=$(cat)

HOOK_INPUT="$INPUT" python3 <<'PY' || true
import json, os, sys

try:
    d = json.loads(os.environ.get("HOOK_INPUT") or "")
except Exception:
    sys.exit(0)

if not isinstance(d, dict):
    sys.exit(0)

session_id = d.get("session_id") or ""
path = d.get("transcript_path") or ""
if not session_id or not path:
    sys.exit(0)

sentinel = "/tmp/claude-memory-nudge-" + session_id
if os.path.exists(sentinel):
    sys.exit(0)

last_signal_idx = None
memory_write_after_signal = False

try:
    with open(path) as f:
        lines = f.readlines()
except Exception:
    sys.exit(0)

for idx, line in enumerate(lines):
    try:
        entry = json.loads(line)
    except Exception:
        continue

    if not isinstance(entry, dict):
        continue

    message = entry.get("message") or {}
    content = message.get("content")

    if entry.get("type") == "user":
        if isinstance(content, str):
            if "Request interrupted by user" in content:
                last_signal_idx = idx
        elif isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_result" and b.get("is_error"):
                    last_signal_idx = idx
        continue

    if not isinstance(content, list):
        continue
    for b in content:
        if not isinstance(b, dict) or b.get("type") != "tool_use":
            continue
        if b.get("name") not in ("Write", "Edit"):
            continue
        file_path = (b.get("input") or {}).get("file_path") or ""
        if "/memory/" in file_path and last_signal_idx is not None and idx > last_signal_idx:
            memory_write_after_signal = True

if last_signal_idx is None or memory_write_after_signal:
    sys.exit(0)

note = (
    "MEMORY CHECK - this session shows a correction-shaped signal "
    "(an interruption or a denied/failed tool call) with no memory file "
    "written since. If something here is worth remembering next time, "
    "save it now using the memory instructions in your system prompt."
)

sentinel_write_succeeded = False
try:
    with open(sentinel, "w") as f:
        f.write("1")
    sentinel_write_succeeded = True
except Exception:
    pass

if sentinel_write_succeeded:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": note,
        },
        "suppressOutput": True,
    }))
PY

exit 0
