---
name: update-github
description: Update all project docs substantively, commit, push, and write a session handoff. Use when the user says "update github". For "deploy", run this first, then the deployment.
---

# Update GitHub

If the project CLAUDE.md defines "update github" differently, follow that instead.

Steps in order:

1. Invoke the handoff skill first - safety net before anything changes.
2. Scan ALL .md files in the project (root, context/, docs/, docs/adr/, anywhere) - do not use a fixed list, find everything that exists. For each file: read its current content, cross-reference against actual session work (git diff + conversation), and make substantive updates (new entries, revised statuses, updated roadmap items, new insights, current metrics). Cosmetic edits or date-only changes are not enough.
3. Run `git status` and `git diff --stat HEAD` to confirm what changed.
4. Commit with a thorough message (use the commit-rules skill).
5. `git push origin HEAD`.
6. Invoke the handoff skill again to capture the final documented state.

## When Things Go Wrong

- **`git push` fails (no upstream, auth error, rejected):** Stop immediately. Report the exact error output to the user. Do not force-push under any circumstance - let the user decide how to proceed.
- **Commit fails due to a pre-commit hook:** Fix the underlying hook issue first (lint error, formatting, secret detected), then re-commit. Never use `--no-verify` to bypass hooks.
- **No .md files have substantive changes:** Still write a minimal update to at least one doc (e.g., add a "YYYY-MM-DD - no changes this session" entry to the relevant STATUS or ROADMAP file) so the subsequent handoff is not empty.
