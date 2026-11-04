---
name: sort-deadlines
description: Use when the user says "sort deadlines" or a session-start note offers it. Marks this project's real open deadlines with Due markers and tags undated items by priority, leaving history alone.
---

# Sort Deadlines

1. Read STATUS.md (Next), the latest handoff and the project's own to-do lists.
2. For each line with a date, decide: real open deadline, or history (something already done or past). Leave history alone.
3. Add `Due YYYY-MM-DD` to the line of each real open deadline or "ideal by" date only. For an item that waits on an event, add `(when <event>)` and a check-again date. An ASAP item with no real date gets a priority tag (step 5), not a date.
   Each item gets ONE marker, in its one home: if the project's own to-do list already holds the item, mark it there and do not repeat the marker in STATUS.md (a STATUS line that only points to the list stays unmarked).
4. Never invent a date. Collect the unclear ones and ask the user in one batched question.
5. Tag every undated open item on its line with `[severity · who · size]`, for example `[high · Claude · quick]`:
   - Severity: `high` = security, money lost or wasted, clients, data. `medium` = blocks other work. `low` = the rest.
   - Who: `Claude` = Claude can do it alone. `you` = needs the owner (a decision, a login, a payment, a call).
   - Size: `quick` = under 15 minutes. Otherwise `big`.
   - Sort: severity first, then quick before big, then file order.
   - The owner's order wins: to put an item above one with a different tag, change its tag; within the same tag, move the line up.
   - Write the tag as plain text on the item's line, never in backticks (backticked tags are treated as examples and ignored).
   - An item with a Due marker gets no tag.
   - Markers and tags never go in handoff, research, decisions or CHANGELOG files (session start skips them).
6. Never edit another project.
7. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/due_markers.py" .` and then the same with `. --next` (the plugin's scripts/due_markers.py; on Windows use `python` or `py` if python3 is missing). Show what is now due and what is next.
8. Commit per update-github.
