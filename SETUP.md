# Get the Team Claude Code Setup (10 minutes)

**Stop babysitting Claude Code.** This setup makes Claude verify its own work, remember your sessions, and stop asking permission for everything - while guardrails block the genuinely dangerous stuff.

Everything here was audited against official Anthropic docs and stress-tested by 200+ research agents in June 2026. The broken advice got thrown out; only what survived verification ships.

## What changes for you

- **Zero permission prompts.** No more pressing "Yes" 200 times a day. Fifteen deny rules block the dangerous commands (rm -rf, force push, reading your credentials) - everything else just runs.
- **Claude checks its own work.** A Stop hook forces a verify-review-complete pass whenever code was written, before Claude tells you it's done. Fewer "done!" messages that aren't.
- **Claude stops repeating its helpers' guesses.** When Claude hands work to a helper agent and the helper reports back, Claude is told how much that helper actually looked at. If the helper opened nothing, Claude is told to check the claim before passing it on to you as fact. You won't see this happen - it works quietly in the background.
- **Claude actually remembers corrections now.** Instead of a manual "lessons" file you had to remember existed, Claude saves what it learns to its own built-in memory automatically. If it forgets to save something worth remembering, a quiet nudge reminds it once per session - you won't see this either unless there's something to log.
- **Your sessions survive.** Handoff files capture state before you run out of context. Open a new session, type `read handoff`, continue where you left off.
- **Structured workflows on demand.** Type "grade this" for rubric-based quality loops, "grill me" to stress-test a plan, "reaudit" to have separate checkers, each taking one part of the work, try to break it, "update docs" to check and tidy the project's notes, "update github" for docs + commit + push + handoff in one command, and "commands" for the full cheat sheet. Plus specialist agents (architect, code-verifier, mechanic) with the right model pre-picked for each job.

## Setup - the easy way (no terminal needed)

**Step 1:** Open Claude Code and paste this whole block as a message:

```
Set up my computer with our team's Claude Code configuration. Do this for me:

1. Download the team setup from https://github.com/Apurv-ed/best-claude-code-setup.git
   into a temporary folder and run claude-setup.py with Python (python3 on Mac,
   python on Windows). It backs up my existing settings automatically and
   installs our team plugin (ap-optimal-claude) by itself. When it finishes,
   give me a one-line summary in plain language.

2. Test the safety net: try to run the command rm -rf /tmp/guardrail-test and
   confirm it gets BLOCKED. Tell me PASS or FAIL in simple words.

3. Then remind me to close and reopen Claude Code so everything loads fresh.

If anything goes wrong, explain it to me simply and tell me exactly what to
post in the team Slack thread.
```

**Step 2:** When Claude says **PASS**, close and reopen Claude Code, then react with a checkmark on the Slack message. Done - you never touch a terminal.

<details>
<summary>Prefer doing it yourself in the terminal? (technical path)</summary>

```bash
git clone https://github.com/Apurv-ed/best-claude-code-setup.git
cd best-claude-code-setup
python3 claude-setup.py    # python claude-setup.py on Windows
```
The installer registers the team plugin marketplace and installs ap-optimal-claude automatically (via the claude CLI). If that step is skipped because `claude` is not on PATH, run inside a session:
```
/plugin marketplace add Apurv-ed/best-claude-code-setup
/plugin install ap-optimal-claude@apurv-ed
```
Then turn on automatic updates: run `/plugin`, open the **Marketplaces** tab, select `apurv-ed`, choose **Enable auto-update** (marketplaces added by hand start with it off).

Verify: restart, `/plugin` shows ap-optimal-claude installed, and asking Claude to run `rm -rf /tmp/guardrail-test` gets blocked. Your settings.json is backed up with a timestamp before it is merged; your own CLAUDE.md is kept.
</details>

## FAQ

**Will this overwrite my personal setup?**
No. The installer merges into settings.json (a timestamped backup is made first) and leaves your own `~/.claude/CLAUDE.md` alone: the team rules live in a separate file, `~/.claude/rules/ap-optimal-claude.md`, which the plugin keeps current. If an older install had put the team rules into your CLAUDE.md, they are moved out and anything you added there is kept (backup in `~/.claude/backups/`).

**I already had Claude Code working fine.**
You'll keep everything you like and gain the verification hooks, guardrails, and session memory. If something feels wrong, your backups are in `~/.claude/` with timestamps and the plugin uninstalls in one command.

**Windows?**
Run `python claude-setup.py` instead. Everything works (plugin skills, agents, guardrails, settings). The six hook scripts are bash: Claude Code runs them through Git Bash automatically if Git for Windows is installed. Five of them also call `python3`, so make sure typing `python3 --version` in Git Bash works; if it doesn't, those hooks can't do their job. Without Git for Windows you still get the full plugin + guardrails; the automatic session-context loading and stop-time self-review just won't run.

**Do I need to update this myself later?**
No. The team plugin is installed with auto-update on, so new skills, agents, hooks, the team rules and new safety blocks arrive automatically: downloaded during one session, active from the next. You should not need to re-run the setup.

**Something broke / question?**
Post in the Slack thread. Known quirk: if `ccx` is not found after install, add `~/.local/bin` to your PATH (the installer prints the exact line).
