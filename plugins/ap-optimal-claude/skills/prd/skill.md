---
name: prd
description: Create a product requirements document before building any significant feature. Creates docs/prd-[feature].md.
---

# PRD Workflow

Use when the user says "prd", "/prd", "write a PRD for", or "product requirements".

## Step 1: Clarify (only if not already clear)

Ask:
- What product or feature area?
- Who are the target users?
- What business outcome does this serve?

## Step 2: Create `docs/prd-[feature-slug].md`

```markdown
# PRD: [Feature Name]
**Date:** YYYY-MM-DD
**Status:** Draft

## Overview
[2-3 sentences: what is this and why does it matter?]

## Problem Statement
[What problem are we solving? Include user pain and business impact.]

## Goals
- [Measurable goal 1]
- [Measurable goal 2]

## Non-Goals
- [Explicitly out of scope]

## User Stories
- As a [user type], I want [action] so that [outcome]

## User Flows

### Happy Path
[Step 1 → Step 2 → Step 3 → Outcome]

### Nothing Works
[Step 1 → Error → What does the user see?]

### Mid-Flow
[Step 1 → Step 2 → Abandon/failure → What state is the user left in?]

## Requirements
| Priority | Requirement | Notes |
|---|---|---|
| P0 | | |
| P1 | | |
| P2 | | |

## Success Metrics
| Metric | Baseline | Target |
|---|---|---|
| | | |

## Open Questions
- [ ] [Question that needs an answer before implementation]

## References
- [Links, related docs, prior art]
```

## Step 3: Next step

After writing the PRD, suggest running `/spec` to break it into a technical spec ready for implementation.
