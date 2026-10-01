#!/usr/bin/env python3
"""Doc check: one home per fact, nothing stale-by-construction.

Run from a project root: python3 doc_check.py [project_dir]
Exit 1 if any ERROR, else 0. WARN lines never fail the check.

ERROR  STATUS.md missing, over 7KB, or End Goal not its first section
ERROR  an "End Goal" section outside STATUS.md (the goal must have one home)
ERROR  a relative Markdown link that points at a file that does not exist
WARN   CLAUDE.md over 200 lines (Anthropic's guidance)
WARN   status-type sections (Now / Next / Done / In Progress / Blockers) outside STATUS.md
WARN   legacy doc files that should be folded (see the project-docs skill)
"""
import pathlib, re, sys

STATUS_MAX_BYTES = 7 * 1024
CLAUDE_MD_MAX_LINES = 200
# Written-once or history files: never "current", so not checked for duplicates or links
FROZEN_DIRS = ("docs/research", "docs/transcriptions", "docs/archive", "docs/plans")
EXEMPT_FROM_STATUS_HEADINGS = ("CHANGELOG.md", "STATUS.md", "docs/SESSION_HANDOFF.md")
STATUS_HEADING = re.compile(r"^##\s+(now|next|next steps|done|in progress|blockers?(\s*/\s*decisions)?)\s*$", re.I)
GOAL_HEADING = re.compile(r"^##\s+end goal\b", re.I)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
LEGACY = ("ROADMAP.md", "EXPERIMENTS.md", "context/state.md", "context/schema.md", "context/insights.md")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".claude"}


def md_files(root):
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        yield p, rel


def headings(text):
    in_code = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("#"):
            yield line.strip()


def check(root):
    errors, warns = [], []
    status = root / "STATUS.md"
    if not status.exists():
        errors.append("STATUS.md is missing (it is the home of the goal, current state and next steps)")
    else:
        size = status.stat().st_size
        if size > STATUS_MAX_BYTES:
            errors.append(f"STATUS.md is {size} bytes, over the {STATUS_MAX_BYTES}-byte limit: move history to CHANGELOG.md")
        h2 = [h for h in headings(status.read_text(encoding="utf-8", errors="ignore")) if h.startswith("## ")]
        if not h2 or not GOAL_HEADING.match(h2[0]):
            errors.append("STATUS.md: the first section must be '## End Goal'")

    for p, rel in md_files(root):
        if rel.startswith(FROZEN_DIRS):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        hs = list(headings(text))
        if rel != "STATUS.md" and any(GOAL_HEADING.match(h) for h in hs):
            errors.append(f"{rel}: has an 'End Goal' section; the goal lives only in STATUS.md (link to it instead)")
        if rel not in EXEMPT_FROM_STATUS_HEADINGS:
            dup = [h for h in hs if STATUS_HEADING.match(h)]
            if dup:
                warns.append(f"{rel}: status-type sections {dup} belong in STATUS.md only")
        for target in LINK.findall(re.sub(r"```.*?```", "", text, flags=re.S)):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
                continue  # URL, mailto:, or in-page anchor
            path = target.split("#", 1)[0]
            if path and not (p.parent / path).resolve().exists():
                errors.append(f"{rel}: broken link -> {target}")
        if rel == "CLAUDE.md":
            n = len(text.splitlines())
            if n > CLAUDE_MD_MAX_LINES:
                warns.append(f"CLAUDE.md is {n} lines (guidance: under {CLAUDE_MD_MAX_LINES}); move detail to skills or docs")

    for rel in LEGACY:
        if (root / rel).exists():
            warns.append(f"{rel}: legacy doc file; fold it into its home (see the project-docs skill)")
    return errors, warns


def main(argv):
    root = pathlib.Path(argv[1] if len(argv) > 1 else ".").resolve()
    errors, warns = check(root)
    for e in errors:
        print(f"ERROR  {e}")
    for w in warns:
        print(f"WARN   {w}")
    print(f"doc-check: {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
