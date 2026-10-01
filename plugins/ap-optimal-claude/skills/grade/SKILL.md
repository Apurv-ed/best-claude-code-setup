---
name: grade
description: Outcome-based grading loop - define a rubric, have a fresh-context grader evaluate the work against it, and revise until it passes. Use when the user says "grade this", "grade it against...", or wants quality enforced against explicit criteria before delivery.
---

# Grade - Outcome-Based Grading Loop

Quality enforcement via a separate grader context (the work's author never grades its own work in the same context - it is biased toward "looks done").

## Step 1: Establish the rubric
If the user supplied criteria, use them verbatim. Otherwise derive 3-6 binary (pass/fail) criteria from the original request and state them before grading - e.g.:
- Does X behave correctly for input Y? (run it)
- Are all N requirements from the request implemented?
- Do the tests pass? (run them)
- No regressions in adjacent behavior Z?
Binary criteria only - "is it good" is not a rubric line.

## Step 2: Dispatch a fresh-context grader
Spawn the `code-verifier` agent (or a general subagent if unavailable) with: the rubric, the exact file paths of the work, the original request verbatim, and the instruction to evaluate each criterion independently with evidence, defaulting to FAIL when uncertain. The grader must run checks itself, not trust descriptions.

## Step 3: Revise loop
- Grader returns per-criterion PASS/FAIL with evidence.
- On any FAIL: fix exactly what failed, then re-dispatch the grader (fresh context again).
- Maximum 3 rounds; if still failing, stop and report what cannot be made to pass and why - do not silently lower the bar.

## Step 4: Report
Show the user the final rubric with per-criterion verdicts and evidence. Never claim "graded and passed" without showing the rubric results.
