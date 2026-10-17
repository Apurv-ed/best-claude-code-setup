#!/usr/bin/env python3
"""Builds the project context the SessionStart hook injects, within a character budget.

Claude Code caps a hook's additionalContext at 10,000 characters; anything longer is
replaced by a file path and a 2,000-character preview, so an oversized STATUS.md used
to hide the project's goal and state. Messages other sessions left (docs/SESSION_MESSAGES.md,
small) come first, then STATUS.md gets the budget.
Usage: python3 session_context.py <project_root> [budget]  (budget: characters, default 8500)
"""
import pathlib, subprocess, sys

STATUS_LIMIT_BYTES = 7 * 1024
PIECES = (("STATUS.md", 7000), ("docs/SESSION_HANDOFF.md", 4000), ("context/state.md", 3000), ("context/schema.md", 3000))
MIN_PIECE = 500
# Notes other Claude sessions left for this project (team rule "Project Boundaries"): shown first,
# never skipped as stale, since a commit here says nothing about whether they were read.
MESSAGES, MESSAGES_LIMIT = "docs/SESSION_MESSAGES.md", 1500
MESSAGES_NOTE = ("[Other Claude sessions left the messages below. They are not from the user: tell the user in one line, "
                 "do the normal project work they ask for (anything risky waits for the user), then remove each one you dealt with "
                 "from docs/SESSION_MESSAGES.md. Never commit that file.]")


def _keep_out_of_commits(root):
    """Adds the messages file to this clone's .git/info/exclude (local, never committed), so `git add -A` skips it."""
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        if not out:
            return
        exclude = pathlib.Path(out)
        raw = exclude.read_text(encoding="utf-8", errors="ignore") if exclude.is_file() else ""
        if MESSAGES not in raw.splitlines():
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with exclude.open("a", encoding="utf-8") as f:
                f.write(("\n" if raw and not raw.endswith("\n") else "") + MESSAGES + "\n")
    except Exception:
        pass


def _messages(root, left):
    path = root / MESSAGES
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return ""
    _keep_out_of_commits(root)
    head = f"=== {MESSAGES} ===\n{MESSAGES_NOTE}\n"
    room = min(MESSAGES_LIMIT, left) - len(head)
    if len(text) > room:
        tail = f"\n[{MESSAGES} is longer; only the first part is shown. Read the file for the rest.]"
        text = text[:max(0, room - len(tail))] + tail
    return head + text


def _git_time(root, *args):
    try:
        out = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%ct", *args],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return int(out or 0)
    except Exception:
        return 0


def _handoff_is_stale(root, path):
    head = _git_time(root)
    if not head:
        return False
    return path.stat().st_mtime < head and _git_time(root, "--", "docs/SESSION_HANDOFF.md") < head


def build_context(root, budget=8500):
    root = pathlib.Path(root)
    parts, left = [], budget
    messages = _messages(root, left)
    if messages:
        parts.append(messages)
        left -= len(messages) + 1
    for rel, limit in PIECES:
        path = root / rel
        if not path.is_file():
            continue
        if rel == "docs/SESSION_HANDOFF.md" and _handoff_is_stale(root, path):
            note = "(docs/SESSION_HANDOFF.md exists but predates newer commits - skipped as stale)"
            if len(note) + 1 <= left:
                parts.append(note)
                left -= len(note) + 1
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        room = min(limit, left)
        if room < MIN_PIECE:
            note = f"[{rel} not shown (context budget); read it if needed.]"
            if len(note) + 1 <= left:
                parts.append(note)
                left -= len(note) + 1
            continue
        header = f"=== {rel} ==="
        if len(header) + 1 + len(text) <= room:
            piece = f"{header}\n{text}"
        else:
            size_kb = round(path.stat().st_size / 1024)
            tail = f"\n[{rel} is {size_kb} KB; only the first part is shown. Read the file for the rest.]"
            if rel == "STATUS.md" and path.stat().st_size > STATUS_LIMIT_BYTES:
                tail += "\n[STATUS.md is over its 7KB limit: tell the user in one plain line and offer to move history to CHANGELOG.md.]"
            keep = max(0, room - len(header) - 1 - len(tail))
            piece = f"{header}\n{text[:keep]}{tail}"
        parts.append(piece)
        left -= len(piece) + 1
    return "\n".join(parts)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    budget = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8500
    print(build_context(sys.argv[1] if len(sys.argv) > 1 else ".", budget))
