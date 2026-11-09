#!/bin/bash
# Session startup: initialize project state in bash, then inject context Claude can read

HOME_DEV="$HOME/Documents/dev"
CWD=$(pwd)
CONTEXT=""
NO_GIT_NOTE=""

# A folder with no git of its own that holds projects (ap/, cf/) is not a project: no notes, no files.
HOLDS_PROJECTS=""
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    for d in "$CWD"/*/.git; do [ -e "$d" ] && HOLDS_PROJECTS=1 && break; done
fi

# Git from the start (ADR-0105): a folder strictly inside the person's projects folder that has no
# git of its own gets a local `git init` (no remote, no GitHub). Fails silent; the notes below then
# see a repo, so [NO GIT] does not also fire.
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/ap-optimal-claude}"
PROJECTS_FOLDER=""
[ -r "$CLAUDE_DIR/projects-folder.txt" ] && PROJECTS_FOLDER=$(head -n 1 "$CLAUDE_DIR/projects-folder.txt" 2>/dev/null | tr -d '\r')
PROJECTS_FOLDER="${PROJECTS_FOLDER%/}"
# Compare real paths, so a symlinked projects folder (or a symlinked cwd) still matches.
PROJECTS_REAL=""
[ -n "$PROJECTS_FOLDER" ] && PROJECTS_REAL=$(cd "$PROJECTS_FOLDER" 2>/dev/null && pwd -P)
IN_CHOSEN=""  # strictly inside the chosen projects folder
if [ -n "$PROJECTS_FOLDER" ] && { [[ "$CWD" == "$PROJECTS_FOLDER"/* ]] || [[ "$(pwd -P 2>/dev/null)" == "$PROJECTS_FOLDER"/* ]] \
        || { [ -n "$PROJECTS_REAL" ] && { [[ "$CWD" == "$PROJECTS_REAL"/* ]] || [[ "$(pwd -P 2>/dev/null)" == "$PROJECTS_REAL"/* ]]; }; }; }; then
    IN_CHOSEN=1
fi
GIT_INIT_NOTE=""
if [ -n "$IN_CHOSEN" ] && [ -z "$HOLDS_PROJECTS" ] && ! git rev-parse --git-dir > /dev/null 2>&1; then
    if git init -q > /dev/null 2>&1; then
        GIT_INIT_NOTE="[GIT STARTED] $(basename "$CWD") had no git; started it here (local only). Tell the user in one line that a first commit is worth making."
    fi
fi

# No git yet: never create a repo here (gh would use whatever account is signed in). Measured
# (no git), at most once a week per folder; Claude asks first, including which GitHub account.
if [[ "$CWD" == "$HOME_DEV"/* ]] && [ -z "$HOLDS_PROJECTS" ] && ! git rev-parse --git-dir > /dev/null 2>&1; then
    MARK_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/ap-optimal-claude}/no-git-noted"
    MARK="$MARK_DIR/$(printf '%s' "$CWD" | cksum | cut -d' ' -f1)"
    if [ -z "$(find "$MARK" -mtime -7 2>/dev/null)" ]; then
        mkdir -p "$MARK_DIR" 2>/dev/null && : > "$MARK" 2>/dev/null
        NO_GIT_NOTE="[NO GIT] $(basename "$CWD") has no git and no online copy. Offer in one line to start git and a private GitHub repo, asking which GitHub account. Do nothing until the user says yes."
    fi
fi

# Online copy check - only in ~/Documents/dev/* or the chosen projects folder: a repo with no remote lives on this computer
# alone. Measured (git has no remote), at most once a week per project (marker in the plugin's
# data folder), and skipped when the folder has no git at all.
ONLINE_NOTE=""
if { [[ "$CWD" == "$HOME_DEV"/* ]] || [ -n "$IN_CHOSEN" ]; } && [ -z "$NO_GIT_NOTE" ] && git rev-parse --git-dir > /dev/null 2>&1 \
        && [ -z "$(git remote 2>/dev/null)" ] && [ "$(git config --get ap.localOnly 2>/dev/null)" != "true" ]; then
    TOP=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$CWD")  # the project, not a subfolder
    MARK_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/ap-optimal-claude}/online-copy-noted"
    MARK="$MARK_DIR/$(printf '%s' "$TOP" | cksum | cut -d' ' -f1)"  # short, unique per project
    if [ -z "$(find "$MARK" -mtime -7 2>/dev/null)" ]; then
        mkdir -p "$MARK_DIR" 2>/dev/null && : > "$MARK" 2>/dev/null
        NAME=$(basename "$TOP")
        ONLINE_NOTE="[NO ONLINE COPY] $NAME has no git remote, so it exists only on this computer. Tell the user in one line and offer a private GitHub repo, asking which account (from $TOP: gh repo create $NAME --private --source=. --push). Not now: drop it (returns weekly). Never wanted: git config ap.localOnly true"
    fi
fi

# STATUS.md check - only in ~/Documents/dev/* or the chosen projects folder
if { [[ "$CWD" == "$HOME_DEV"/* ]] || [ -n "$IN_CHOSEN" ]; } && [ -z "$HOLDS_PROJECTS" ] && [ ! -f STATUS.md ]; then
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

. "$(dirname "$0")/lib-python.sh"
if [ -z "$PYTHON" ]; then
    # Without Python the JSON cannot be built safely, so this one fixed message is written by hand.
    printf '%s' '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "[SETUP] Python 3 was not found, so the setup\u0027s automatic helpers (session context, self-review, setup updates) are off. Tell the user this in one line and offer to install Python 3 for them (Windows: winget install Python.Python.3.12; Mac: xcode-select --install)."}}'
    exit 0
fi

# Projects folder (ADR-0105): once per person, ask where projects are kept. The folder guard
# (scripts/safety_guard.py) points here when it refuses to change files in Documents or Downloads.
FOLDER_NOTE=""
SAFETY="${CLAUDE_PLUGIN_ROOT}/scripts/safety_guard.py"
if [ ! -f "$CLAUDE_DIR/projects-folder.txt" ] && [ ! -e "$PLUGIN_DATA/projects-folder-asked" ] && [ -r "$SAFETY" ] \
        && mkdir -p "$PLUGIN_DATA" 2>/dev/null && : > "$PLUGIN_DATA/projects-folder-asked" 2>/dev/null; then
    CANDS=$("$PYTHON" "$SAFETY" --candidates 2>/dev/null | tr '\n' ';' | sed 's/;$//; s/;/; /g')
    FOLDER_NOTE="[PROJECTS FOLDER] Ask the user once which folder to keep projects in (Claude changes files only in a project folder, not in home, Documents, Downloads or Desktop). Recommend ~/Claude Projects"
    [ -n "$CANDS" ] && FOLDER_NOTE="$FOLDER_NOTE; folders that already exist and could be used instead: $CANDS"
    FOLDER_NOTE="$FOLDER_NOTE. On their answer run: \"$PYTHON\" \"$SAFETY\" --set-folder \"<folder>\" and tell them to start Claude in a project folder inside it. Do not ask again."
fi

# Project context (STATUS.md first, then a fresh handoff, then legacy context/ files),
# kept under Claude Code's 10,000-character hook cap by scripts/session_context.py.
# A committed .claude/settings.json holding one computer's paths protects nothing elsewhere.
# Measured first, so the project context shrinks by the note's length and stays under the cap.
PATHS_NOTE=""
[ -f "$CWD/.claude/settings.json" ] && PATHS_NOTE=$("$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/machine_paths.py" --session "$CWD" 2>/dev/null)
BUDGET=$((8800 - ${#PATHS_NOTE})); [ "$BUDGET" -lt 0 ] && BUDGET=0
PROJECT_CONTEXT=$("$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/session_context.py" "$CWD" "$BUDGET" 2>/dev/null)
[ -n "$PROJECT_CONTEXT" ] && CONTEXT="$CONTEXT"$'\n'"$PROJECT_CONTEXT"
[ -n "$PATHS_NOTE" ] && CONTEXT="$CONTEXT"$'\n'"$PATHS_NOTE"
[ -n "$ONLINE_NOTE" ] && CONTEXT="$CONTEXT"$'\n'"$ONLINE_NOTE"

# Installer version check - notify in-session if team member needs to re-run
MIN_VER_FILE="${CLAUDE_PLUGIN_ROOT}/min_installer_version"
CUR_VER_FILE="$HOME/.claude/.installer_version"
if [ -f "$MIN_VER_FILE" ] && [ -f "$CUR_VER_FILE" ]; then
    MIN_VER=$(tr -d '[:space:]' < "$MIN_VER_FILE")
    CUR_VER=$(tr -d '[:space:]' < "$CUR_VER_FILE")
    if [ "$CUR_VER" -lt "$MIN_VER" ] 2>/dev/null; then
        # ON_WINDOWS comes from lib-python.sh; Windows shells do not expand ~
        if [ -n "$ON_WINDOWS" ]; then
            UPDATE_CMD='in PowerShell: python "$HOME\.claude\claude-setup.py" (or py instead of python)'
        else
            UPDATE_CMD='in Terminal: python3 ~/.claude/claude-setup.py'
        fi
        CONTEXT="$CONTEXT"$'\n'"[SETUP UPDATE REQUIRED] Tell the user this at the start of your response: 'Your Claude Code setup needs an update. Please run this command $UPDATE_CMD' Do not proceed until you have surfaced this message."
    fi
fi

# Keep the installed setup current from the plugin (team rules, add-only deny rules,
# one-time migrations). All logic lives in scripts/sync_setup.py, which the installer
# also runs, so there is one implementation. Changes it makes take effect next session.
SYNC_NOTES=$("$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/sync_setup.py" 2>/dev/null)
if [ -n "$SYNC_NOTES" ]; then
    CONTEXT="$CONTEXT"$'\n'"[SETUP UPDATED] Mention in one short line at the start of your response:"$'\n'"$SYNC_NOTES"
fi

# Daily self-update (scripts/self_update.py): reports what the last background run did and,
# at most once a day, starts the next one detached, so this never waits for the network.
UPDATE_NOTES=$("$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/self_update.py" check 2>/dev/null)
if [ -n "$UPDATE_NOTES" ]; then
    CONTEXT="$CONTEXT"$'\n'"[SETUP NOTE] Tell the user each in one line at the start of your response:"$'\n'"$UPDATE_NOTES"
fi

# Legacy tasks/lessons.md (pre-migration, not yet ported to Auto Memory): tell Claude to use it
LESSONS_NOTE=""
[ -f "$CWD/tasks/lessons.md" ] && LESSONS_NOTE="This project still has tasks/lessons.md (old-style lessons). Read it silently now and apply its rules for this session."

# One-time note per project introducing Due markers (due_markers.py --intro writes its own marker file)
DUE_INTRO_NOTE=""
if { [[ "$CWD" == "$HOME_DEV"/* ]] || [ -n "$IN_CHOSEN" ]; } && [ -z "$HOLDS_PROJECTS" ]; then
    DUE_TOP=$(git rev-parse --show-toplevel 2>/dev/null)
    if [ -n "$DUE_TOP" ] && [ -f "$DUE_TOP/STATUS.md" ]; then
        DUE_INTRO_NOTE=$("$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/due_markers.py" --intro "${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/ap-optimal-claude}" "$DUE_TOP" 2>/dev/null)
    fi
fi

# Append instruction Claude will actually see (additionalContext, not systemMessage)
STARTUP_MSG=$'\n[SESSION START]'
[ -n "$NO_GIT_NOTE" ] && STARTUP_MSG="$STARTUP_MSG $NO_GIT_NOTE"
[ -n "$GIT_INIT_NOTE" ] && STARTUP_MSG="$STARTUP_MSG $GIT_INIT_NOTE"
[ -n "$FOLDER_NOTE" ] && STARTUP_MSG="$STARTUP_MSG $FOLDER_NOTE"
[ -n "$LESSONS_NOTE" ] && STARTUP_MSG="$STARTUP_MSG $LESSONS_NOTE"
[ -n "$DUE_INTRO_NOTE" ] && STARTUP_MSG="$STARTUP_MSG $DUE_INTRO_NOTE"
CONTEXT="$CONTEXT$STARTUP_MSG"

printf '%s' "$CONTEXT" | "$PYTHON" -c "
import json, sys
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': sys.stdin.read()}}, ensure_ascii=False))
"
