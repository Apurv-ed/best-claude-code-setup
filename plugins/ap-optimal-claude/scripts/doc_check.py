#!/usr/bin/env python3
"""Doc check: one home per fact, nothing stale-by-construction.

Run from a project root: python3 doc_check.py [project_dir] [--changed]
Exit 1 if any ERROR, else 0. WARN lines never fail the check.
--changed: only files touched in git (uncommitted or untracked) can fail the check;
errors in other files are shown as warnings.

ERROR  STATUS.md missing, over 7KB, or End Goal not its first section
ERROR  an "End Goal" section outside STATUS.md (the goal must have one home)
ERROR  a relative Markdown link that points at a file that does not exist
WARN   a broken link in CHANGELOG.md (history may name deleted files)
WARN   decision records in docs/decisions/: bad file name, duplicate number, no status, bad "superseded by"
WARN   docs/decisions.md (single log; the standard is one file per decision)
WARN   .md files at the root or in docs/ that are not a standard home
WARN   STATUS.md End Goal still the placeholder
WARN   CLAUDE.md over 200 lines (Anthropic's guidance)
WARN   status-type sections (Now / Next / Done / In Progress / Blockers) outside STATUS.md
WARN   legacy doc files that should be folded (see the project-docs skill)
Paths listed in an optional .doc-check-ignore (one prefix per line) are skipped, e.g. backups.
"""
import pathlib, re, subprocess, sys

STATUS_MAX_BYTES = 7 * 1024
CLAUDE_MD_MAX_LINES = 200
# Written-once or history files: never "current", so not checked for links or status headings
FROZEN_DIRS = ("docs/research", "docs/transcriptions", "docs/archive", "docs/plans",
               "docs/adr", "docs/superpowers", "docs/decisions")
HISTORY_FILES = ("CHANGELOG.md",)  # broken links here are warnings only
KNOWN_DOCS = {"STATUS.md", "README.md", "CHANGELOG.md", "CLAUDE.md", "CLAUDE.local.md", "AGENTS.md",
              "METRICS.md", "CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md", "CODE_OF_CONDUCT.md",
              "LICENSE.md", "docs/SESSION_HANDOFF.md", "docs/decisions.md"}
MADR_NAME = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
STATUS_LINE = re.compile(r"^\s*(?:[*-]\s*)?status:\s*(.*?)\s*$", re.I | re.M)
PLACEHOLDER_GOAL = "[describe the end goal here]"
MAX_UNLISTED_SHOWN = 8
EXEMPT_FROM_STATUS_HEADINGS = ("CHANGELOG.md", "STATUS.md", "docs/SESSION_HANDOFF.md")
STATUS_HEADING = re.compile(r"^##\s+(now|next|next steps|done|in progress|blockers?(\s*/\s*decisions)?)\s*$", re.I)
GOAL_HEADING = re.compile(r"^##\s+end goal\b", re.I)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
LEGACY = ("ROADMAP.md", "EXPERIMENTS.md", "context/state.md", "context/schema.md", "context/insights.md")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".claude", ".superpowers"}


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


def ignored_prefixes(root):
    """Extra frozen paths from an optional .doc-check-ignore (one path prefix per line, # comments)."""
    f = root / ".doc-check-ignore"
    if not f.exists():
        return ()
    return tuple(l.strip().rstrip("/") + "/" for l in f.read_text().splitlines() if l.strip() and not l.startswith("#"))


def madr_findings(root):
    """Warnings for docs/decisions/*.md (one file per decision, MADR style)."""
    d = root / "docs" / "decisions"
    if not d.is_dir():
        return []
    warns, numbers, statuses = [], {}, {}
    for p in sorted(d.glob("*.md")):
        if p.name in ("README.md", "index.md"):
            continue
        rel = f"docs/decisions/{p.name}"
        if not MADR_NAME.match(p.name):
            warns.append(f"{rel}: file name should look like 0001-short-title.md (4 digits, lowercase, hyphens)")
        else:
            numbers.setdefault(p.name[:4], []).append(p.name)
        m = STATUS_LINE.search(p.read_text(encoding="utf-8", errors="ignore"))
        if not m or not m.group(1).strip("\"' *"):
            warns.append(f"{rel}: no status (add 'status: accepted' front matter or a 'Status:' line)")
        else:
            statuses[rel] = m.group(1).strip("\"' *")
    for num, names in sorted(numbers.items()):
        if len(names) > 1:
            warns.append(f"docs/decisions/: duplicate number {num}: {', '.join(names)}")
    for rel, st in sorted(statuses.items()):
        if "superseded by" in st.lower():
            targets = re.findall(r"(?<!\d)(\d{4})(?!\d)", st)
            if not targets or not all(t in numbers for t in targets):
                warns.append(f"{rel}: 'superseded by' must name an existing decision number (e.g. ADR-0042); got '{st}'")
    return warns


def unknown_docs(root, ignored):
    """One WARN line listing .md files at the root or in docs/ that are not a standard home."""
    names = []
    for p, rel in md_files(root):
        if rel.count("/") > (1 if rel.startswith("docs/") else 0):
            continue
        if rel in KNOWN_DOCS or rel.startswith(FROZEN_DIRS + ignored):
            continue
        names.append(rel)
    if not names:
        return None
    shown = ", ".join(names[:MAX_UNLISTED_SHOWN])
    more = f", ... (+{len(names) - MAX_UNLISTED_SHOWN} more)" if len(names) > MAX_UNLISTED_SHOWN else ""
    return ("unlisted docs (not a standard home; fold into a home, move to docs/archive/, "
            f"or list in .doc-check-ignore): {shown}{more}")


def check(root, changed=None):
    errors, warns = [], []
    frozen = FROZEN_DIRS + ignored_prefixes(root)
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
        if PLACEHOLDER_GOAL in status.read_text(encoding="utf-8", errors="ignore"):
            warns.append("STATUS.md: the End Goal is still the placeholder; ask the user for it")

    for p, rel in md_files(root):
        if rel.startswith(frozen):
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
                (warns if rel in HISTORY_FILES else errors).append(f"{rel}: broken link -> {target}")
        if rel == "CLAUDE.md":
            n = len(text.splitlines())
            if n > CLAUDE_MD_MAX_LINES:
                warns.append(f"CLAUDE.md is {n} lines (guidance: under {CLAUDE_MD_MAX_LINES}); move detail to skills or docs")

    for rel in LEGACY:
        if (root / rel).exists():
            warns.append(f"{rel}: legacy doc file; fold it into its home (see the project-docs skill)")
    if (root / "docs" / "decisions.md").exists():
        warns.append("docs/decisions.md: single decision log; the standard is one file per decision in docs/decisions/ "
                     "(ask the user before converting; see the project-docs skill)")
    warns.extend(madr_findings(root))
    unlisted = unknown_docs(root, ignored_prefixes(root))
    if unlisted:
        warns.append(unlisted)
    if changed is not None:
        kept = []
        for e in errors:
            path = "STATUS.md" if e.startswith("STATUS.md") else e.split(":", 1)[0] if ":" in e else None
            if path is None or path in changed:
                kept.append(e)
            else:
                warns.append(f"{e} (not in this change)")
        errors = kept
    return errors, warns


def changed_files(root):
    """Project-relative paths touched since HEAD (uncommitted, staged, untracked); None if git fails."""
    cmds = (["git", "diff", "--name-only", "--relative", "HEAD"], ["git", "diff", "--name-only", "--relative", "--staged"],
            ["git", "ls-files", "--others", "--exclude-standard"])
    out = set()
    try:
        for c in cmds:
            r = subprocess.run(c, cwd=root, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return None
            out.update(l.strip() for l in r.stdout.splitlines() if l.strip())
    except (OSError, subprocess.SubprocessError):
        return None
    return out


def main(argv):
    args = [a for a in argv[1:] if a != "--changed"]
    root = pathlib.Path(args[0] if args else ".").resolve()
    errors, warns = check(root, changed_files(root) if "--changed" in argv else None)
    for e in errors:
        print(f"ERROR  {e}")
    for w in warns:
        print(f"WARN   {w}")
    print(f"doc-check: {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
