---
name: commit-rules
description: Detailed commit message format and rules. Use when creating git commits.
---

# Commit Message Format

Every commit must be **thorough and detailed**. Never minimal. Follow this format:

```
type(scope): short summary

detailed description of what changed and WHY - at least 2-3 sentences

Changes:
- specific change with file/component name
- specific change with file/component name
```

**Types:** feat, fix, refactor, docs, style, test, chore, perf, ci, build

**Rules:**
- Summary must be clear to someone unfamiliar with the project.
- Description MUST explain **why**, not just what. What problem does this solve?
- List ALL affected files/components.
- **Never write** fix stuff, updates, WIP, or single-line messages for multi-file changes.
- If writing less than 5 lines for a multi-file commit, it is not thorough enough.

## Documentation Check (before committing)

Update each fact the commit changes in its ONE home (project-docs skill). Skip
files that haven't changed - no boilerplate updates, no copying a fact into a
second file.

- **STATUS.md** - goal, Now / Next, blockers changed?
- **CHANGELOG.md** - an entry under [Unreleased] for user-visible changes
- **docs/decisions/** - a new decision file, only when a real decision (with a reason) was made
- **README.md / CLAUDE.md** - only if setup, usage or conventions changed
- **METRICS.md** - only if the project measures something and it moved

Then run the doc check (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_check.py"`).
