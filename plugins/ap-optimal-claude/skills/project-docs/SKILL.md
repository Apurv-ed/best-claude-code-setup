---
name: project-docs
description: Project documentation system - creates and maintains ROADMAP.md, METRICS.md, EXPERIMENTS.md, context/, docs/adr/, docs/research/. Use at session start when STATUS.md exists but ROADMAP.md does not, or whenever creating or structuring project docs.
---

# Project Documentation System

If STATUS.md exists and ROADMAP.md does not, create ROADMAP.md, METRICS.md, and `context/` immediately - before any other work.

## ROADMAP.md
Outcome-focused, not a feature list. Sections: End Goal (one sentence), Now, Next, Later, Completed, Risks.
- Now/Next/Later: outcomes, not tasks
- Risks table: Risk | Likelihood (1-5) | Impact (1-5) | Mitigation - keep to 3-5 risks max
Update after completing any milestone or shifting direction.

## METRICS.md
How we measure success. Table: Metric | Baseline | Target | Current | Last Updated.
Update at each milestone checkpoint.

## EXPERIMENTS.md
For AI/ML projects and product experiments. Prevents repeating failed experiments.
Each entry: Date, Hypothesis, Method, Result, Conclusion, Next Step.
Skip for pure infrastructure/refactoring work.

## context/ directory
AI-optimized snapshot for fast session restoration. Update after every logical milestone.
- `context/state.md` - current phase, immediate next action, recent changes, blockers
- `context/schema.md` - data structures, interfaces, API contracts, environment variables
- `context/decisions.md` - tactical/operational decisions (tooling, process, config) + one-line reasoning
- `context/insights.md` - discoveries, gotchas, non-obvious learnings

Note: `context/decisions.md` is for operational decisions. Technology/architecture choices (framework, database, irreversible patterns) belong in `docs/adr/` instead. Do not duplicate entries between the two.

## docs/adr/ (Architecture Decision Records)
One file per architectural decision: `docs/adr/NNN-title.md`
Fields: Status, Context, Decision, Consequences, Alternatives Considered.
Append-only - never edit past ADRs, write a new one to supersede.
Create when: choosing a framework, database, architecture pattern, or any hard-to-reverse decision.

## docs/research/
Save reference material, papers, and external docs here before reading so they are available next session. Name files: `YYYY-MM-DD-[topic].md`. Keep a one-line description at the top of each file.
