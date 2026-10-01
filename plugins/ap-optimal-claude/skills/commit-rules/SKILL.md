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

Update relevant project docs to reflect the work being committed. Skip files
that haven't changed - don't add boilerplate updates.

- **STATUS.md** - always check; update if state, progress, or blockers changed
- **ROADMAP.md** - update if a milestone completed or direction shifted
- **METRICS.md** - update if measurable progress was made
- **context/state.md** - update if phase, next action, or blockers changed
- **EXPERIMENTS.md** - update if an experiment concluded (AI/ML projects only)
