---
name: startup
description: Run at the start of every new session. Lists relevant skills for the project.
---

# Session Startup

The hook has already handled git repo creation and STATUS.md. Your job here is two things:

## Step 1: Memory Context

Auto Memory has already been loaded into context automatically by Claude Code itself (not by this project's session-start hook) - do not re-read it. If a legacy `tasks/lessons.md` still exists in this project root (pre-migration, not yet ported), read it silently and apply its rules for this session too.

## Step 2: Relevant Skills

From the available skills list, pick 3-5 most relevant to this project and list them:
`- skill-name: one line on what it does`

## Step 3: Summary

One line: `Session ready | memory: [auto-loaded]`

Note: context usage is shown in the status line. Long sessions cost more of the plan with every message and can drift; at 40% the user types `handoff`. Do not schedule reminder wakeups - they re-read the whole conversation at cold-cache prices.
