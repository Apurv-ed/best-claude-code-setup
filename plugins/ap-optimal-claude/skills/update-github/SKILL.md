---
name: update-github
description: Use when the user says "update github" (or before "deploy"). Updates each changed fact in its one home doc, runs the doc check, commits and pushes.
---

# Update GitHub

If the project CLAUDE.md defines "update github" differently, follow that instead.

Steps in order:

1. List what this session changed (`git status`, `git diff --stat HEAD`, the conversation).
2. Update each changed fact in its ONE home (see the project-docs skill): STATUS.md (Now / Next / Blockers, goal if it moved), CHANGELOG.md (one dated entry), docs/decisions.md (only for real decisions), README.md / CLAUDE.md (only if setup, usage or conventions changed). Delete or correct any other file that now states something stale. Do not touch files that did not change; no filler "no changes" entries.
3. Run the doc check from the project root: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_check.py"`. Fix every ERROR before committing.
4. Commit with a thorough message (use the commit-rules skill), then `git push origin HEAD`.
5. If work is unfinished, invoke the handoff skill; otherwise STATUS.md already is the handoff.

## When Things Go Wrong

- **`git push` fails (no upstream, auth error, rejected):** Stop immediately. Report the exact error output to the user. Do not force-push under any circumstance - let the user decide how to proceed.
- **Commit fails due to a pre-commit hook:** Fix the underlying hook issue first (lint error, formatting, secret detected), then re-commit. Never use `--no-verify` to bypass hooks.
- **The doc check cannot run (no python3):** say so, do the checks by eye (STATUS.md size, one End Goal, no broken links), and continue.
