#!/bin/bash
# Session startup: initialize project state in bash, then inject context Claude can read

HOME_DEV="$HOME/Documents/dev"
CWD=$(pwd)
CONTEXT=""
REPO_CREATED=""

# Git repo check - only in ~/Documents/dev/*
if [[ "$CWD" == "$HOME_DEV"/* ]] && ! git rev-parse --git-dir > /dev/null 2>&1; then
    FOLDER=$(basename "$CWD")
    if [ ! -f .gitignore ]; then
        printf 'node_modules/\n.env\n.env.*\n__pycache__/\n*.pyc\n.DS_Store\n.venv/\nvenv/\ndist/\nbuild/\n*.log\n' > .gitignore
    fi
    git init -q && git add . && git commit -q -m "chore: initial commit" 2>/dev/null
    if gh repo create "$FOLDER" --private --source=. --push --quiet 2>/dev/null; then
        REPO_CREATED="GitHub repo '$FOLDER' created and pushed."
    else
        REPO_CREATED="git init done but gh repo create failed (name collision or gh not authed)."
    fi
fi

# STATUS.md check - only in ~/Documents/dev/*
if [[ "$CWD" == "$HOME_DEV"/* ]] && [ ! -f STATUS.md ]; then
    cat > STATUS.md << 'STATUSMD'
# Project Status

## End Goal
[describe the end goal here]

## Done
- nothing yet

## In Progress
- nothing yet

## Next Steps
- nothing yet

## Blockers / Decisions
- none
STATUSMD
fi

# Load context files (skip the handoff once newer commits exist - STATUS.md and
# context/ carry the current state by then, and a stale handoff wastes ~5KB of
# context every session)
if [ -f docs/SESSION_HANDOFF.md ]; then
    HANDOFF_FRESH=1
    if git rev-parse --git-dir > /dev/null 2>&1; then
        HEAD_TIME=$(git log -1 --format=%ct 2>/dev/null); HEAD_TIME=${HEAD_TIME:-0}
        HANDOFF_COMMIT_TIME=$(git log -1 --format=%ct -- docs/SESSION_HANDOFF.md 2>/dev/null); HANDOFF_COMMIT_TIME=${HANDOFF_COMMIT_TIME:-0}
        HANDOFF_MTIME=$(stat -f %m docs/SESSION_HANDOFF.md 2>/dev/null || stat -c %Y docs/SESSION_HANDOFF.md 2>/dev/null); HANDOFF_MTIME=${HANDOFF_MTIME:-0}
        if [ "$HANDOFF_MTIME" -lt "$HEAD_TIME" ] && [ "$HANDOFF_COMMIT_TIME" -lt "$HEAD_TIME" ]; then
            HANDOFF_FRESH=0
        fi
    fi
    if [ "$HANDOFF_FRESH" -eq 1 ]; then
        CONTEXT="$CONTEXT\n=== SESSION_HANDOFF.md ===\n$(cat docs/SESSION_HANDOFF.md)"
    else
        CONTEXT="$CONTEXT\n(docs/SESSION_HANDOFF.md exists but predates newer commits - skipped as stale; STATUS.md and context/ below are current)"
    fi
fi

if [ -f STATUS.md ]; then
    CONTEXT="$CONTEXT\n=== STATUS.md ===\n$(cat STATUS.md)"
fi

# Load context directory files for AI session restoration
if [ -f context/state.md ]; then
    CONTEXT="$CONTEXT\n=== context/state.md ===\n$(cat context/state.md)"
fi
if [ -f context/schema.md ]; then
    CONTEXT="$CONTEXT\n=== context/schema.md ===\n$(cat context/schema.md)"
fi

# Installer version check - notify in-session if team member needs to re-run
MIN_VER_FILE="${CLAUDE_PLUGIN_ROOT}/min_installer_version"
CUR_VER_FILE="$HOME/.claude/.installer_version"
if [ -f "$MIN_VER_FILE" ] && [ -f "$CUR_VER_FILE" ]; then
    MIN_VER=$(tr -d '[:space:]' < "$MIN_VER_FILE")
    CUR_VER=$(tr -d '[:space:]' < "$CUR_VER_FILE")
    if [ "$CUR_VER" -lt "$MIN_VER" ] 2>/dev/null; then
        CONTEXT="$CONTEXT\n[SETUP UPDATE REQUIRED] Tell the user this at the start of your response: 'Your Claude Code setup needs an update. Please run this command in Terminal: python3 ~/.claude/claude-setup.py' Do not proceed until you have surfaced this message."
    fi
fi

# Append instruction Claude will actually see (additionalContext, not systemMessage)
STARTUP_MSG="\n[SESSION START]"
[ -n "$REPO_CREATED" ] && STARTUP_MSG="$STARTUP_MSG $REPO_CREATED"
STARTUP_MSG="$STARTUP_MSG Invoke the startup skill now (Skill tool, skill=\"startup\") to list relevant skills. IMPORTANT: Watch the context % in the status bar - quality degrades past 40%. Type 'handoff' the moment it hits 40%, before continuing work."
CONTEXT="$CONTEXT$STARTUP_MSG"

PYTHON=$(command -v python3 || command -v python) 2>/dev/null
[ -z "$PYTHON" ] && exit 0

echo -e "$CONTEXT" | $PYTHON -c "
import json, sys, os

# Push managed settings keys to settings.json (takes effect on next Claude restart).
# SCALAR keys only - the loop below does a flat overwrite (s[k] = v), so never add
# merge-semantics keys like 'permissions' here or it would clobber a user's own rules.
# Deny-rule changes must go through re-running the installer, not this hook.
# 'model' was removed in 1.5.1: forcing it every session silently overwrote each
# person's own /model choice (e.g. back to opusplan = Sonnet for execution).
# The installer still sets opusplan for NEW installs only.
MANAGED = {'skillListingBudgetFraction': 0.02}
sp = os.path.expanduser('~/.claude/settings.json')
try:
    with open(sp) as f:
        s = json.load(f)
    if any(s.get(k) != v for k, v in MANAGED.items()):
        for k, v in MANAGED.items():
            s[k] = v
        with open(sp, 'w') as f:
            json.dump(s, f, indent=2)
except Exception:
    pass  # skip migration if settings.json is missing or unparseable

content = sys.stdin.read()
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': content}}))
"
