---
name: sort-deadlines
description: Use when the user says "sort deadlines" or a session-start note offers it. Marks this project's real open deadlines with Due markers, leaving history alone.
---

# Sort Deadlines

1. Read STATUS.md (Next), the latest handoff and the project's own to-do lists.
2. For each line with a date, decide: real open deadline, or history (something already done or past). Leave history alone.
3. Add `Due YYYY-MM-DD` to the line of each real open deadline only. For an item that waits on an event, add `(when <event>)` and a check-again date.
4. Never invent a date. Collect the unclear ones and ask the user in one batched question.
5. Never edit another project.
6. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/due_markers.py" .` (the plugin's scripts/due_markers.py; on Windows use `python` or `py` if python3 is missing) and show what is now due.
7. Commit per update-github.
