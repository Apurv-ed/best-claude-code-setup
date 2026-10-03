---
name: update-github
description: Use when the user says "update github" (or before "deploy"). Does the quick doc update (each changed fact in its one home doc), runs the doc check on changed files, commits and pushes.
---

# Update GitHub

If the project CLAUDE.md defines "update github" differently, follow that instead.

Steps in order:

1. List what this session changed (`git status`, `git diff --stat HEAD`, the conversation).
2. Do the quick doc update from the project-docs skill: put each fact this session changed in its one home (STATUS.md, CHANGELOG.md under [Unreleased], a decision file for real decisions (in a project that still has the single `docs/decisions.md`, append to it in its existing style and never start `docs/decisions/` beside it), README.md / CLAUDE.md when setup, usage or conventions changed). The full audit runs only when the user says "update docs".
3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_check.py" --changed` from the project root and fix every ERROR it reports.
4. Commit with a thorough message (use the commit-rules skill), then `git push origin HEAD`.
5. If work is unfinished, invoke the handoff skill; otherwise STATUS.md already is the handoff.

## When Things Go Wrong

- **`git push` fails (no upstream, auth error, rejected):** Stop immediately. Report the exact error output to the user. Do not force-push under any circumstance - let the user decide how to proceed.
- **Commit fails due to a pre-commit hook:** Fix the underlying hook issue first (lint error, formatting, secret detected), then re-commit. Never use `--no-verify` to bypass hooks.
- **The doc check cannot run (no python3):** say so, do the checks by eye (STATUS.md size, one End Goal, no broken links), and continue.
