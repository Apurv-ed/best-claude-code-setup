---
name: fix
description: Structured bug fix workflow. Creates tasks/fix-[bug].md as a persistent artifact then invokes systematic debugging.
---

# Fix Workflow

Use when the user says "fix", "/fix", reports a bug, or pastes an error/traceback.

## Step 1: Create `tasks/fix-[bug-slug].md`

```markdown
# Fix: [Bug Description]
**Date:** YYYY-MM-DD
**Status:** Investigating

## Bug Report
[Exact error, symptoms, or failing behavior]

## Reproduction Steps
1.
2.

## Suspected Root Cause
[Initial hypothesis - update as you investigate]

## Fix Approach
[What will be changed and why]

## Verification
- [ ] Bug no longer reproduces
- [ ] Related tests pass
- [ ] No regressions introduced

## Root Cause (post-fix)
[Fill in after fix confirmed]
```

## Step 2: Investigate

Invoke `superpowers:systematic-debugging` to work through the root cause systematically.

## Step 3: Update the artifact

After the fix is confirmed working:
- Set Status: Resolved
- Fill in Root Cause section
- Check off all Verification items

## When Things Go Wrong

- **Fix causes other tests to fail:** Stop. Re-triage from scratch using the new failure set - do not patch forward on top of a broken fix. Update the fix file with the new symptom set and restart systematic-debugging.
- **Fix doesn't work after the first attempt:** Do not guess-and-check. Return to `superpowers:systematic-debugging` with the updated evidence. Guessing wastes cycles and masks the real root cause.
- **Bug cannot be reproduced:** Document every reproduction attempt tried (env, inputs, conditions) in the fix file. Set Status to "Cannot Reproduce" and close the file. Do not leave it as "Investigating" indefinitely.
