---
name: commands
description: Use when the user types "commands", asks what they can type or say, asks which commands or shortcuts exist, or wants the cheat sheet. Shows the quick reference of phrases and Claude Code shortcuts.
---

# Commands cheat sheet

Show the user the tables below as they are. Keep it plain: no extra jargon, no long intro. If they ask about one item, explain it in one or two plain sentences. This file is the source for the cheat sheet on the public landing page (`own-site/index.html`, section `commands`); a test keeps the two in step.

## Added by this setup

| Say | What it does |
|---|---|
| `update docs` | Checks and tidies this project's notes. Nothing goes to GitHub. |
| `update github` | Tidies the notes, then saves your work to GitHub. |
| `end session` | Wraps up: tidies all the notes, saves a handoff note if work is unfinished, then saves everything to GitHub. |
| `deploy` | Runs update github, then publishes the project if it has a publish step. |
| `handoff` | Writes a note so a fresh session continues where you left off. Use it once /context shows about 40% full. |
| `ooc` | Means "running out of context". Saves a handoff note right away. |
| `read handoff` | Continues from the last handoff note. Type it at the start of a new session. |
| `grill me` | Questions your plan until every decision is clear. |
| `grade this` | Checks the work against a checklist and improves it until it passes. |
| `fix all tests` | Fixes failing tests and re-runs them until they all pass. |
| `commands` | Shows this list inside Claude Code. /ap-optimal-claude:commands also works. |

## Built into Claude Code

| Type | What it does |
|---|---|
| `/clear` | Starts a new conversation with a clean slate. Use it between tasks to keep Claude sharp and save usage. |
| `/resume` | Reopens an earlier conversation. |
| `/model` | Switches to a different Claude model. |
| `/usage` | Shows how much of your plan you have used, and the cost. |
| `/context` | Shows how full this conversation is. |
| `/rewind` | Goes back to an earlier point in the conversation, with the option to undo code changes too. |
| `/mcp` | Manages add-on connections and their sign-ins. Sign in to Context7 (up-to-date library docs) once. |
| `/doctor` | Runs a checkup on your setup. |

## Keys and symbols

| Press or type | What it does |
|---|---|
| `Esc` | Stops Claude mid-answer so you can redirect it. Work done so far is kept. |
| `Shift+Tab` | Cycles through permission modes, including plan mode, where Claude plans before changing anything. On Windows, use Alt+M if Shift+Tab does nothing. |
| `!` | Runs a terminal command when typed at the start of a line. Claude sees the output. |
| `@` | Points Claude at a file. Type it, then pick the file from the list. |
