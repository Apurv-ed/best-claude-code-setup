---
name: handoff
description: Session handoff template. Use when the user types "handoff" or "handoff <project>". Writes SESSION_HANDOFF.md for the current or named project.
---

# Session Handoff

## Determine the target project

- If the user typed `handoff <name>` (e.g. `handoff my-app`), the target project is `~/Documents/dev/<name>/`.
- If the user just typed `handoff`, the target project is the current working directory.

## Gather context for the target project

Run these in parallel on the target project directory:

```bash
cd <target_project> && git log --oneline -15
cd <target_project> && git diff HEAD --stat
cd <target_project> && git status --short
```

Also read `<target_project>/STATUS.md` and `<target_project>/docs/SESSION_HANDOFF.md` (if they exist) for prior context. Do NOT re-read files you already have in context.

Use the conversation history (if available) + git output to reconstruct what was happening. If conversation history for the target project is not available (cross-session handoff), note that in the handoff and reconstruct from git state + any snippet the user provided.

## Write the handoff

Create or overwrite `<target_project>/docs/SESSION_HANDOFF.md`:

```markdown
# Session Handoff - [DATE]

## What We Were Doing
[1-2 sentence summary of the task/goal]

## What Was Completed This Session
- [bullet list of everything finished, with file paths where relevant]

## Current State
[Exact state - what is working, what is broken, what is in progress. Include a table if helpful.]

## The Open Bug / Blocker (if any)
[If the session ended mid-debug, describe the bug, what was tried, and the leading hypothesis for the fix.]

## Next Steps (in order)
1. [First thing to do in the next session]
2. [Second thing]

## Key Files Changed
- path/to/file - what changed and why

## Commands To Know
[Any commands being used / needed to continue]

## Decisions Made
[Architectural or approach decisions so we do not re-debate them]

## Warnings / Gotchas
[Anything that would trip up a fresh session - known bugs, workarounds, etc.]
```

## After writing

Say: "Handoff written to `docs/SESSION_HANDOFF.md` in `<project>`. Now: 1. Type `/exit`  2. Run `claude -c` to resume  3. Say *read the handoff* and I will pick up exactly where we left off."

## Note on cross-session handoffs

If the user pasted a snippet of the other session's chat, use it - it captures mid-debug state that git cannot. If no snippet was provided, note in the handoff that conversation history was unavailable and the reconstruction is based on git state only.

## When Things Go Wrong

- **Git state is dirty and uncommittable (merge conflicts, detached HEAD, untracked secrets):** Do not attempt to commit. Instead, run `git diff HEAD` and paste the raw output into the handoff under an "Uncommitted Changes" section so the next session can recover the work.
- **SESSION_HANDOFF.md can't be written (permission error, missing `docs/` dir):** Fall back to writing `HANDOFF.md` in the project root. Note in the file that it is in the root due to a write error, and remind the user to move it to `docs/` once the permission issue is resolved.
