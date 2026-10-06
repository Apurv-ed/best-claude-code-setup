---
name: reaudit
description: Use when the user types "reaudit", "reaudit project" or "reaudit <path or topic>", or explicitly asks for a thorough multi-angle audit of finished work or a whole project (double-check everything, poke holes, simulate, cross-question, audit end to end).
---

# Reaudit

Separate checkers attack the work, each owning one part of it, each in its own fresh context, so none of them shares the author's belief that it is done. Every finding must be proven or it does not count.

## Step 1: Scope and claims

- `reaudit`: everything this session changed or claimed. Collect the changed files (`git status`, `git diff`, commits made this session) and anything changed outside git.
- `reaudit project`: the whole project, judged against the End Goal in STATUS.md.
- `reaudit <path or topic>`: only that.
- If you cannot tell what this session did (after /clear, no git, or `git status` also shows other work), ask the user one question: what should be audited?

Then write two lists, which go to every checker:
1. **The request**, in the user's own words (copy it, do not summarize).
2. **Every claim made**: "tests pass", "works on X", "N files", "fixed", "nothing else uses this", each number given. A claim nobody re-checked is a guess.

## Step 2: Plan the checkers from the work itself

Split the work by its own parts and risks, and give each checker one of them, named in plain words. For example, a website change: Copy, Tracking and security, Videos, Safari live check. A data report: Totals, Source files, Categories. Use the fewest checkers that cover the parts, since every checker costs plan usage: a small change gets 2, most work 3-5, `reaudit project` up to 6.

Then check coverage. Each of these duties must be owned by at least one named checker (one checker can own several), or be marked "not applicable" with a one-line reason. They are what a self-check forgets:
- **Promises:** every part of the request was done, and every claim holds against the raw source.
- **Real use:** used the way a real person would, in the real place (the live site, a fresh clone, a real browser or phone), including when things go wrong (no network, interrupted, asleep, other time zone).
- **Edge cases:** empty, huge, odd characters, missing files, running twice; the full test suite if there is one.
- **Safety:** secrets, private data, anything deleted or hard to undo, cost, other projects or accounts.
- **Approach:** the assumptions behind the work tested, and "is this the best way?" compared with 2 alternatives, using current docs online, not memory.

Real actions: if the only real proof needs a real action (submit the live form, send a test email, a test payment), list those now and ask the user once, before launching, whether to include them and with which test data.

Agent: `general-purpose` for anything that runs, browses or researches; `ap-optimal-claude:code-verifier` for checking claims and files.

## Step 3: Send the checkers, all in one message

Launch them together so they run at the same time. Each prompt contains: its part and the duties it owns, the scope (exact paths, URLs, git range), the request and the claims list, and these rules:
- Try to prove the work WRONG; reporting nothing is fine, padding is not.
- Tag every finding `[REPRODUCED: exact command and output]` or `[UNVERIFIED: what it was inferred from]`, with severity (high / medium / low) and `file:line` or URL.
- Look at real things freely: load the live site, play the video, open it in a browser, run read-only queries. Change nothing real: experiments, throwaway tests and copies go in a temp folder; no edits to project files or settings, no scheduled jobs, no push, no deploy, no messages, no form submissions, no paid or account calls (except real actions the user approved in Step 2), nothing in other projects. If the only proof is a real change, describe the test and stop; the orchestrator asks the user.
- Only one checker runs the full test suite; the others run single, targeted commands (keeps the computer cool).
- Final response under 2000 characters.

Do not tell checkers what you think is fine. That is the bias they exist to avoid.

## Step 4: Cross-examine the findings

Checkers are wrong too. For each high or medium finding:
- `REPRODUCED`: run the command yourself and confirm you see the same thing.
- `UNVERIFIED`: try to reproduce it, inside a temp copy. Put every one you cannot reproduce into ONE fresh `ap-optimal-claude:code-verifier`, told to REFUTE each. Keep only those that survive.
- Merge duplicates. Mark refuted findings as refuted; never drop them silently.

## Step 5: Fix and re-check

- Proven defects in this session's own work: fix them, run the full tests, then send only the checker that found each defect again (fresh agent). At most 2 rounds.
- Ask first before: a change of approach, anything outside the scope, anything destructive or hard to undo.

## Step 6: Report

1. One line verdict: holds up / holds up after fixes / has open problems.
2. Table: severity | finding | proof | status (fixed, needs you, refuted).
3. "Checked and held up": one line per checker, by its plain name, on what was tried and survived, so the user can see the depth.
4. Questions for the user, last.

## Red Flags (stop and redo the step)

- A finding marked fixed with no test run after the fix.
- "Probably fine" or "should work" for anything a command could check.
- A duty from Step 2 with no checker owning it, or checkers launched one after another.
- Checkers named after generic angles when the work has obvious parts of its own.
- Reporting a checker's finding without reproducing it.
