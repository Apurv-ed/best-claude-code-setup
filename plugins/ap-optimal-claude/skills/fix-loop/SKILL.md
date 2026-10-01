---
name: fix-loop
description: Use when tests are failing and you need autonomous fix-test-fix iteration until all tests pass. Trigger on "fix all tests", "make tests green", "fix the test suite", or when multiple test failures need systematic resolution.
---

# Autonomous Fix Loop

Iteratively fix failing tests until the full suite passes, with a hard cap to prevent infinite loops.

## Process

### 1. Run Full Suite

```bash
pytest --tb=short -q
```

Capture the output. If all tests pass, stop - nothing to do.

### 2. Triage Failures

Before fixing anything, group and prioritize:

1. **Group by error type/module** - failures with the same stack trace or in the same module likely share a root cause
2. **Identify cascading failures** - if module A is broken, tests in modules B and C that import A will also fail. Fix root causes first.
3. **Identify bad tests** - a test is wrong if: it asserts behavior that contradicts documented requirements, was written against a previous API version that intentionally changed, has hardcoded values that no longer match current schema, or the "fix" to pass it would break other tests. Check `git blame` to see if the test or its source changed more recently.
4. **Fix root causes first**, re-run, and see how many failures disappear before addressing the next group.

### 3. Fix Each Failure Group

For each failure group from triage:

1. **Read the test file** and the source file it tests
2. **Diagnose the root cause** - bug in source, bad test, or cascading from another failure?
3. **Fix the source code** (not the test) unless the test itself is wrong
4. **Re-run that specific test** to confirm the fix: `pytest path/to/test.py::test_name --tb=short`
5. If it still fails, re-diagnose and try again (max 3 attempts per test)
6. If 3 attempts fail, flag as UNRESOLVED in FIX_LOG.md with diagnosis

### 4. Re-run Full Suite

After fixing all groups, run the full suite again. New failures may have appeared from interactions between fixes.

### 5. Loop

Repeat steps 1-4 until either:
- All tests pass
- 10 full iterations completed (hard cap)
- Two consecutive iterations produce no change in failing tests (stalled - exit early)

### 6. Write FIX_LOG.md

After each iteration, append to `FIX_LOG.md` in the project root (use the Write tool, not heredocs):

```markdown
## Iteration N - [timestamp]
- Tests passing: X/Y
- Fixed: [list of tests fixed and what was wrong]
- Remaining failures: [list with brief diagnosis]
- Files changed: [list]
```

At hard cap or early exit, add a Final Summary:

```markdown
## Final Summary
- Total tests fixed: X
- Total iterations: N
- Remaining failures: [list with full diagnosis, whether present since iteration 1, suspected root cause]
- Recommended next steps: [e.g., "These appear to be bad tests" or "Requires architectural changes"]
```

## Rules

- **Fix source code, not tests** - unless the test is genuinely wrong (see triage criteria above)
- **During the fix loop, operate autonomously** without asking for input. If truly ambiguous, log it in FIX_LOG.md and move on.
- **Only parallelize fixes that affect different source files.** If multiple failures trace to the same module, fix them sequentially.
- **Stop at 10 iterations** or when progress stalls (no change in 2 consecutive iterations)
- **Never introduce new failures** - if a fix breaks other tests, revert it and try a different approach
- **Commit after each iteration that reduces failing test count** - preserves progress even if suite never goes fully green. Follow project commit message format.

## Quick Reference

| Step | Command | Stop if |
|------|---------|---------|
| Full suite | `pytest --tb=short -q` | All pass |
| Single test | `pytest path::test -v` | Passes |
| Check coverage | `pytest --tb=short -q` after fixes | New failures appear |
| Hard cap | Count iterations | 10 reached |
| Stall detection | Compare failing tests | No change in 2 iterations |
