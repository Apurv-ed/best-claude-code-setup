---
name: project-docs
description: Use when the user says "update docs", or when creating, restructuring or cleaning up a project's documentation, or when a project still has legacy doc files (ROADMAP.md, context/, EXPERIMENTS.md, a single docs/decisions.md). Defines the one-home-per-fact doc set, the standard formats, and the full "update docs" pass.
---

# Project Documentation: one home per fact

Principle (Google docguide, Write the Docs): a small set of fresh, accurate docs beats a large set in disrepair; incorrect docs are worse than missing ones; every fact lives in one place and everything else links to it.

## The doc set

| Fact | Home | Notes |
|---|---|---|
| End goal, current state, next steps, blockers | `STATUS.md` | End Goal first. Sections: End Goal, Now, Next, Later (optional), Blockers. Under 7KB (loaded every session). No history here. |
| What changed and when | `CHANGELOG.md` | Keep a Changelog 1.1.0: `## [Unreleased]` on top, then dated sections; entries grouped under `### Added / Changed / Deprecated / Removed / Fixed / Security`; written by hand for humans. |
| Why a decision was made | `docs/decisions/NNNN-title.md` | One file per decision in MADR 4 format (template below). A reversed decision gets `status: "superseded by ADR-NNNN"`; never rewritten. `docs/decisions/README.md` lists them. |
| How to set up and use | `README.md` | Standard Readme order: title, short description, Install, Usage, then links to the other docs; Contributing and License when public. |
| Instructions for Claude | `CLAUDE.md` | Commands, conventions, gotchas. Under 200 lines. No status or history. |
| Research, transcripts | `docs/research/YYYY-MM-DD-topic.md`, `docs/transcriptions/` | Written once with a one-line summary at the top; not kept "current". |
| Unfinished work between sessions | `docs/SESSION_HANDOFF.md` | Temporary; ignored by the session hook once newer commits exist. |

Create other files only when there is real content: `METRICS.md` when the project measures something; nothing "just in case".

## Templates

Decision file (`docs/decisions/NNNN-title.md`, minimal MADR):

```markdown
---
status: "accepted"
date: YYYY-MM-DD
---
# Short title of the decision

## Context and Problem Statement
Two or three sentences.

## Considered Options
* Option A
* Option B

## Decision Outcome
Chosen option: "Option A", because <reason>.

### Consequences
* Good, because ...
* Bad, because ...
```

## Rules
- Update the home of a fact in the same change as the work. When a fact changes, fix it in its home and delete copies elsewhere.
- Never put the same fact in two files. If a second file needs it, link: `see STATUS.md#next`.
- Before committing doc changes, run the doc check: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_check.py"` from the project root (add `--changed` to block only on files this change touches), and fix what it reports.

## "update docs": the full pass
1. Put every fact this session changed in its one home (STATUS, CHANGELOG under [Unreleased], a new decision file for each real decision, README, CLAUDE.md). Delete stale copies elsewhere.
2. Instruction files: run the built-in audit by invoking the Skill tool with skill `claude-api` and args `prompt-audit` (whole setup) or `prompt-audit <path>`. It reports only; apply the fixes that are clearly right, and separately check that every file or command it mentions exists (it can miss missing files).
3. Other current docs (README, STATUS, CHANGELOG [Unreleased], METRICS, docs/*.md that are not history): compare each claim with the code and config. Scope: files and code changed since the last commit whose subject starts with `docs(audit)` (`git log --grep '^docs(audit)' -1 --format=%H`); the first time, the whole doc set. Never read whole data folders.
4. Decisions: every decision that a newer one reverses has `status: "superseded by ADR-NNNN"`.
5. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_check.py"` and fix its ERRORs; fix WARNs that are quick and clearly right.
6. Commit as `docs(audit): <summary>` (that subject marks the scope for next time).
7. Tell the user at most 5 plain lines: what changed, anything that needs them. Never use the words MADR, supersede, WARN or ERROR with the user.

## Converting an existing project (ask first)
If the project has `docs/decisions.md`, an old changelog layout, or legacy files, ask ONE plain question, e.g. "This project's notes use an older layout. I can reorganise them into the standard one (about N files change; nothing is lost and the old version stays in history). Do it now?" On yes: do only that conversion, in its own commit. On no: do not ask again in this session, and append new decisions to the existing `docs/decisions.md` in its own style; never start `docs/decisions/` next to it. N = the number of files the conversion will create, change or delete.

Splitting `docs/decisions.md`:
- One file per `##` entry, oldest = 0001; title from the heading, `date:` from the heading date.
- Keep the body verbatim: Chose -> "Decision Outcome", Because -> "Context and Problem Statement", Trade-off -> "Consequences". If an entry lacks those labels, keep its whole body under "Decision Outcome".
- Omit "Considered Options" when the entry names no alternatives; never invent options.
- Status from markers: `SUPERSEDED`, `reverses`, `supersedes` -> `superseded by ADR-NNNN` on the older entry.
- Write `docs/decisions/README.md` as a numbered list of links; delete `docs/decisions.md`; update links to it.

Converting an old changelog: add `## [Unreleased]` on top and keep the existing dated sections as they are; new entries go under Added / Changed / Deprecated / Removed / Fixed / Security. Do not rewrite history.

## Folding legacy files (ROADMAP.md, context/*, EXPERIMENTS.md, docs/adr/)
Propose this to the user before doing it; it is a one-time cleanup per project:
1. `ROADMAP.md`: goal -> STATUS End Goal (keep one copy); Now/Next/Later -> STATUS; Completed -> CHANGELOG (if not already there); Not Doing / risks -> a decision file in `docs/decisions/`. Then delete ROADMAP.md.
2. `context/state.md` -> STATUS (current state) and CHANGELOG (recent changes). Delete.
3. `context/schema.md` -> README (interfaces, env vars for humans) or CLAUDE.md (gotchas for Claude). Delete.
4. `context/decisions.md`, `docs/adr/*` -> `docs/decisions/` (one file per decision; existing ADR files may be moved there).
5. `context/insights.md` -> CLAUDE.md (gotchas Claude must know) or a decision file (lessons with a reason). Delete.
6. `EXPERIMENTS.md`: keep only if the project runs experiments; otherwise fold results into decisions.
Git history is the backup: say which commit holds the old files. Run the doc check after.
