---
name: project-docs
description: Use when creating, restructuring or cleaning up a project's documentation, or when a project still has legacy doc files (ROADMAP.md, context/, EXPERIMENTS.md). Defines the one-home-per-fact doc set and how to fold legacy files into it.
---

# Project Documentation: one home per fact

Principle (Google docguide, Write the Docs): a small set of fresh, accurate docs beats a large set in disrepair; incorrect docs are worse than missing ones; every fact lives in one place and everything else links to it.

## The doc set

| Fact | Home | Notes |
|---|---|---|
| End goal, current state, next steps, blockers | `STATUS.md` | End Goal first. Sections: End Goal, Now, Next, Later (optional), Blockers. Under 7KB (loaded every session). No history here. |
| What changed and when | `CHANGELOG.md` | Newest first, dated, one short entry per change, written for humans. |
| Why a decision was made | `docs/decisions.md` | Dated entry: Chose / Because / Trade-off. A reversed decision gets "SUPERSEDED by <date>", never rewritten. |
| How to set up and use | `README.md` | For humans. Link to other docs, don't copy them. |
| Instructions for Claude | `CLAUDE.md` | Commands, conventions, gotchas. Under 200 lines. No status or history. |
| Research, transcripts | `docs/research/YYYY-MM-DD-topic.md`, `docs/transcriptions/` | Written once with a one-line summary at the top; not kept "current". |
| Unfinished work between sessions | `docs/SESSION_HANDOFF.md` | Temporary; ignored by the session hook once newer commits exist. |

Create other files only when there is real content: `METRICS.md` when the project measures something; nothing "just in case".

## Rules
- Update the home of a fact in the same change as the work. When a fact changes, fix it in its home and delete copies elsewhere.
- Never put the same fact in two files. If a second file needs it, link: `see STATUS.md#next`.
- Before committing doc changes, run the doc check: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_check.py"` from the project root, and fix what it reports.

## Folding legacy files (ROADMAP.md, context/*, EXPERIMENTS.md, docs/adr/)
Propose this to the user before doing it; it is a one-time cleanup per project:
1. `ROADMAP.md`: goal -> STATUS End Goal (keep one copy); Now/Next/Later -> STATUS; Completed -> CHANGELOG (if not already there); Not Doing / risks -> `docs/decisions.md`. Then delete ROADMAP.md.
2. `context/state.md` -> STATUS (current state) and CHANGELOG (recent changes). Delete.
3. `context/schema.md` -> README (interfaces, env vars for humans) or CLAUDE.md (gotchas for Claude). Delete.
4. `context/decisions.md`, `docs/adr/*` -> `docs/decisions.md` (ADR files may stay and be linked from it).
5. `context/insights.md` -> CLAUDE.md (gotchas Claude must know) or `docs/decisions.md` (lessons with a reason). Delete.
6. `EXPERIMENTS.md`: keep only if the project runs experiments; otherwise fold results into decisions.
Git history is the backup: say which commit holds the old files. Run the doc check after.
