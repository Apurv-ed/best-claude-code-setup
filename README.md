# Claude Code Best Practices

Save tokens, reduce costs, and get better results from Claude Code.

Based on official Anthropic documentation, community benchmarks, and real-world testing: safer defaults (hard blocks on destructive commands, a safety check on risky actions), leaner context, and skills and hooks that keep sessions on track.

## Get Started

### Easiest: let Claude Code do it

Open Claude Code and paste this:

```
Set up my Claude Code with https://github.com/Apurv-ed/best-claude-code-setup . First explain in plain words what it will change on my computer and wait for my OK. Then back up my current Claude settings, clone the repo and run its installer (python3 claude-setup.py), and tell me what changed.
```

Your existing settings are backed up before anything changes, your own `~/.claude/CLAUDE.md` is left alone, and updates arrive automatically afterwards.

### Interactive Setup Wizard (recommended)

Step-by-step guide designed for non-technical users. Takes about 10 minutes.

Open [`index.html`](index.html) in your browser or view online: [apurv-ed.github.io/best-claude-code-setup](https://apurv-ed.github.io/best-claude-code-setup/)

The wizard walks you through:
1. Choosing between fresh install or smart optimizer
2. Running the setup command
3. Verifying it works
4. Installing recommended plugins
5. Learning essential commands
6. Saving money with best practices

### Quick Option A: Fresh Install

New to Claude Code or want optimized defaults? One-command setup (backs up your existing files):

```bash
git clone https://github.com/Apurv-ed/best-claude-code-setup.git
cd best-claude-code-setup
python3 claude-setup.py || python claude-setup.py
```

Then use `ccx` instead of `claude` to start.

### Quick Option B: Smart Optimizer

Have existing settings you want to keep? Claude analyzes your setup and merges best practices without overwriting customizations:

```bash
git clone https://github.com/Apurv-ed/best-claude-code-setup.git
cd best-claude-code-setup/smart-optimizer
claude
```

Claude will automatically walk you through the recommendations.

### Option C: Read the Full Guide

Open [`claude-code-best-practices.html`](claude-code-best-practices.html) in your browser for a visual, non-technical guide. Save as PDF with Cmd+P / Ctrl+P.

Or view it online: [apurv-ed.github.io/best-claude-code-setup/claude-code-best-practices.html](https://apurv-ed.github.io/best-claude-code-setup/claude-code-best-practices.html)

## What Gets Configured

| Setting | What it does | Impact |
|---------|-------------|--------|
| MAX_THINKING_TOKENS=10000 | Caps thinking tokens on older models (current models use the effort level instead) | Lower thinking cost on those models |
| Context Efficiency rules | Stops Claude from echoing, narrating, re-reading | Major output reduction |
| Safety deny rules | Blocks recursive deletes, force pushes, and reading .env files | Protects your work and secrets |

## Recommended Plugins

After setup, start a Claude Code session and install these:

```
/plugin install superpowers@claude-plugins-official      # Structured workflows (planning, TDD, code review)
/plugin install context7@claude-plugins-official          # Always-current library documentation
/plugin install code-simplifier@claude-plugins-official   # Code quality reviews
```

## Contributing

Found a tip that saves tokens? Open a PR or issue.

## License

MIT
