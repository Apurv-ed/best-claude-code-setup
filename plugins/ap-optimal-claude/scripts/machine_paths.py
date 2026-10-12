#!/usr/bin/env python3
"""Finds machine-specific paths (one person's home folder) in files a project shares.

A committed path into one person's home folder (/Users/<name>/...) works on one computer only. In a committed
.claude/settings.json it is worse than broken: the permission rule matches nothing on a
teammate's machine, so a protection quietly does not apply there. Write(path) rules are
flagged too: Claude Code accepts them but never checks them (it checks Edit and Read).

Used by doc_check.py (WARN lines) and by the SessionStart hook (one note per session while
a committed settings file holds machine paths). Fails silent.
Usage: python3 machine_paths.py --session <project_root>
"""
import json, pathlib, re, subprocess, sys

SETTINGS = ".claude/settings.json"
# A home folder followed by a real name (any alphabet). Mac /Users/x, Windows C:\Users\x
# (also JSON-escaped C:\\Users\\x) and C:/Users/x, Git Bash /c/Users/x or //c/Users/x, and
# Linux /home/x (settings only: in docs a /home/<page> path is usually a web route).
# A name may not start with $ or %, or hold { ( %: /Users/$USER and C:\Users\%USERNAME% are
# the portable forms. Mac and Git Bash forms are case-sensitive ("/users/123" is a web
# route); the drive-letter form is not (Windows paths are often typed in lowercase).
_NAME = r"([^\s/\\\"'`<>()\[\]{}:*|,;?#$%]+)"
# Not inside a word, a relative path (./ ~/) or a variable; after ":" only when it is not a drive
# letter (so "src:/Users/x" and "PATH=...:/Users/x" count, "C:/Users/x" is matched once below).
_START = r"(?<![\w.~$%])(?<!\b[A-Za-z]:)"
USERS_PATH = re.compile(_START + r"/{1,2}(?:[a-zA-Z]/)?Users/" + _NAME
                        + r"|" + _START + r"//[a-zA-Z]/(?i:users)/" + _NAME  # permission-rule form, any case
                        + r"|(?<![\w])[a-zA-Z]:(?:\\{1,2}|/)(?i:users)(?:\\{1,2}|/)" + _NAME)
LINUX_HOME = re.compile(_START + r"/{1,2}home/" + _NAME)
# Generic stand-ins only: a real first name (John, Alice) is a real machine path.
PLACEHOLDERS = {"name", "username", "user", "you", "yourname", "me", "someone", "example",
                "jdoe", "johndoe", "shared", "public", "default", "defaultuser", "all", "guest",
                "runner", "x", "xxx", "yourusername", "myname", "yourusernamehere"}
WRITE_RULE = re.compile(r"\bWrite\([^)\n\"]+\)")
DATED = re.compile(r"\d{4}-\d{2}-\d{2}|(?<!\d)20\d{6}(?!\d)")
HISTORY_DIRS = {"research", "transcriptions", "archive", "plans", "sessions", "handoffs"}


def is_record(rel):
    """Dated or history files stay as written: CHANGELOG, a session handoff, the retired lessons log,
    dated names or folders (2026-06-11 or 20260611), history folders."""
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1].upper()
    return (name.startswith("CHANGELOG") or name in ("SESSION_HANDOFF.MD", "LESSONS.MD")
            or any(DATED.search(p) for p in parts)
            or any(p.lower() in HISTORY_DIRS for p in parts[:-1]))


def find(text, linux=True):
    """Distinct machine paths in text, as written (placeholders like <name>, YOUR_NAME or ... are skipped)."""
    out = []
    matches = list(USERS_PATH.finditer(text)) + (list(LINUX_HOME.finditer(text)) if linux else [])
    for m in matches:
        name = next(g for g in m.groups() if g)
        if re.sub(r"[-_.]", "", name.lower()) in PLACEHOLDERS or name.strip(".") == "":
            continue
        hit = m.group(0)
        if hit not in out:
            out.append(hit)
    return out


def tracked(root, rel):
    try:
        return subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", rel],
                              capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


def settings_findings(root):
    """Problems in a git-tracked .claude/settings.json, one plain sentence each."""
    root = pathlib.Path(root)
    path = root / SETTINGS
    if not path.is_file() or not tracked(root, SETTINGS):
        return []
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return []
    found = []
    paths, seen = [], set()
    for p in find(text):  # //Users/x and /Users/x are the same folder: list it once
        if p.lstrip("/") not in seen:
            seen.add(p.lstrip("/"))
            paths.append(p)
    if paths:
        found.append(f"{SETTINGS} (committed) holds machine paths {', '.join(paths[:3])}: those folders do not exist "
                     "on another computer, so rules naming them protect nothing there and settings using them break; "
                     "move them to .claude/settings.local.json (gitignored)")
    found.extend(write_rule_findings(text))
    return found


def write_rule_findings(text):
    """Write(path) rules, which Claude Code never checks, with advice that fits allow vs deny."""
    try:
        perms = json.loads(text).get("permissions") or {}
        lists = {k: [r for r in perms.get(k) or [] if isinstance(r, str) and WRITE_RULE.fullmatch(r)]
                 for k in ("deny", "ask", "allow")}
    except (ValueError, AttributeError):  # not strict JSON (e.g. comments): cannot tell allow from deny
        rules = WRITE_RULE.findall(text)
        return [f"{SETTINGS}: {', '.join(rules[:3])} is never checked by Claude Code (it checks Edit and Read rules); "
                "delete it, and use an Edit(...) rule for that path instead"] if rules else []
    out = []
    blocking = lists["deny"] + lists["ask"]
    if blocking:
        out.append(f"{SETTINGS}: {', '.join(blocking[:3])} is never checked by Claude Code (it checks Edit and Read "
                   "rules), so it protects nothing; delete it, and protect that path with an Edit(...) rule if none does yet")
    if lists["allow"]:
        out.append(f"{SETTINGS}: {', '.join(lists['allow'][:3])} is never checked by Claude Code; delete it "
                   "(an Edit(...) allow rule is what lets Claude write those files)")
    return out


def session_note(root):
    found = settings_findings(root)
    if not found:
        return ""
    has_paths = any("holds machine paths" in f for f in found)
    found = [f if len(f) <= 400 else f[:397] + "..." for f in found]  # a huge path must not crowd out the context
    tail = (" (machine paths go in the gitignored .claude/settings.local.json; make sure .gitignore lists it)"
            if has_paths else "")
    label = "[PORTABLE PATHS] " if has_paths else "[CLAUDE SETTINGS] "
    return label + ". ".join(found) + ". Tell the user this in one plain line and offer to fix it" + tail + "."


if __name__ == "__main__":
    try:
        if len(sys.argv) > 2 and sys.argv[1] == "--session":
            note = session_note(sys.argv[2])
            if note:
                print(note)
    except Exception:
        pass
