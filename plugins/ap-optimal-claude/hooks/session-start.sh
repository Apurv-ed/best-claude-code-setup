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

## Now
- nothing yet

## Next
- nothing yet

## Blockers
- none
STATUSMD
fi

PYTHON=$(command -v python3 || command -v python) 2>/dev/null
[ -z "$PYTHON" ] && exit 0

# Project context (STATUS.md first, then a fresh handoff, then legacy context/ files),
# kept under Claude Code's 10,000-character hook cap by scripts/session_context.py.
PROJECT_CONTEXT=$("$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/session_context.py" "$CWD" 2>/dev/null)
[ -n "$PROJECT_CONTEXT" ] && CONTEXT="$CONTEXT"$'\n'"$PROJECT_CONTEXT"

# Installer version check - notify in-session if team member needs to re-run
MIN_VER_FILE="${CLAUDE_PLUGIN_ROOT}/min_installer_version"
CUR_VER_FILE="$HOME/.claude/.installer_version"
if [ -f "$MIN_VER_FILE" ] && [ -f "$CUR_VER_FILE" ]; then
    MIN_VER=$(tr -d '[:space:]' < "$MIN_VER_FILE")
    CUR_VER=$(tr -d '[:space:]' < "$CUR_VER_FILE")
    if [ "$CUR_VER" -lt "$MIN_VER" ] 2>/dev/null; then
        CONTEXT="$CONTEXT"$'\n'"[SETUP UPDATE REQUIRED] Tell the user this at the start of your response: 'Your Claude Code setup needs an update. Please run this command in Terminal: python3 ~/.claude/claude-setup.py' Do not proceed until you have surfaced this message."
    fi
fi

# Keep the installed setup current from the plugin (team rules, add-only deny rules,
# one-time migrations). All logic lives in scripts/sync_setup.py, which the installer
# also runs, so there is one implementation. Changes it makes take effect next session.
SYNC_NOTES=$("$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/sync_setup.py" 2>/dev/null)
if [ -n "$SYNC_NOTES" ]; then
    CONTEXT="$CONTEXT"$'\n'"[SETUP UPDATED BY THE TEAM PLUGIN] Mention these in one short line at the start of your response:"$'\n'"$SYNC_NOTES"
fi

# Append instruction Claude will actually see (additionalContext, not systemMessage)
STARTUP_MSG=$'\n[SESSION START]'
[ -n "$REPO_CREATED" ] && STARTUP_MSG="$STARTUP_MSG $REPO_CREATED"
STARTUP_MSG="$STARTUP_MSG Invoke the startup skill now (Skill tool, skill=\"ap-optimal-claude:startup\") to list relevant skills. IMPORTANT: Watch the context % in the status bar - quality degrades past 40%. Type 'handoff' the moment it hits 40%, before continuing work."
CONTEXT="$CONTEXT$STARTUP_MSG"

printf '%s' "$CONTEXT" | $PYTHON -c "
import json, sys
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': sys.stdin.read()}}))
"
