#!/usr/bin/env python3
"""Keep an installed setup current from the plugin, the single source of truth.

Run by the SessionStart hook every session and by claude-setup.py right after it installs
the plugin. Every step is idempotent, never removes anything a person wrote, and fails
silent (a broken sync must never break a session). Prints one short line per change made,
which the hook passes on so Claude can mention it.

Steps:
1. Team rules: write ~/.claude/rules/ap-optimal-claude.md (platform note + rules/core.md)
   when it differs. Personal rules live in other files in that folder and are never touched.
2. Old installer CLAUDE.md: if ~/.claude/CLAUDE.md is the old installer output, back it up
   and keep only the sections a person added, since the team rules now come from step 1.
3. Duplicate skills: back up and remove ~/.claude/skills/<name> only when it is a byte-exact
   copy of a skill some installer version wrote (the plugin ships the current version).
4. Settings: add any missing baseline deny rule (add-only), keep the scalar MANAGED keys,
   and ONCE switch defaultMode bypassPermissions -> auto (a later choice is respected).

Usage: python3 sync_setup.py   (needs CLAUDE_PLUGIN_ROOT, or pass --plugin-root DIR)
"""
import hashlib, json, os, re, sys, time
from pathlib import Path

MANAGED_SCALARS = {"skillListingBudgetFraction": 0.02}
RULES_NAME = "ap-optimal-claude.md"
RULES_HEADER = ("<!-- Managed by the ap-optimal-claude plugin: refreshed every session, edits here are overwritten.\n"
                "     Put personal rules in another file in this folder. -->\n# Claude Code Instructions (team rules)\n\n")
MIGRATION_MARKER = "migrations.json"


def platform_name():
    if sys.platform == "darwin":
        return "mac"
    if sys.platform.startswith("win") or os.environ.get("MSYSTEM"):
        return "windows"
    return "linux"


def backup(path: Path, claude_dir: Path) -> None:
    dest = claude_dir / "backups"
    dest.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = dest / f"{path.name}.{stamp}"
    if path.is_dir():
        import shutil
        shutil.copytree(path, target)
    else:
        target.write_bytes(path.read_bytes())


def sync_rules(root: Path, claude_dir: Path, notes: list) -> set:
    core = (root / "rules" / "core.md").read_text(encoding="utf-8")
    plat = (root / "rules" / f"platform-{platform_name()}.md").read_text(encoding="utf-8")
    content = RULES_HEADER + plat.rstrip("\n") + "\n\n" + core
    target = claude_dir / "rules" / RULES_NAME
    if not target.exists() or target.read_text(encoding="utf-8") != content:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        notes.append("team rules updated (~/.claude/rules/ap-optimal-claude.md)")
    return {h.strip() for h in re.findall(r"(?m)^## .+$", content)}


def split_sections(text: str):
    """Return (preamble, [(heading, block)]) split on level-2 headings outside code fences."""
    pre, sections, cur, in_code = [], [], None, False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith("## "):
            cur = [line.strip(), [line]]
            sections.append(cur)
        elif cur is None:
            pre.append(line)
        else:
            cur[1].append(line)
    return "".join(pre), [(h, "".join(b)) for h, b in sections]


def migrate_claude_md(claude_dir: Path, managed_headings: set, legacy: dict, notes: list) -> None:
    path = claude_dir / "CLAUDE.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if not text.startswith("# Claude Code Instructions\n"):
        return  # not an installer-written file: leave it alone
    known = managed_headings | set(legacy.get("claude_md_headings", []))
    pre, sections = split_sections(text)
    kept = [block for heading, block in sections if heading not in known]
    if len(kept) == len(sections):
        return
    backup(path, claude_dir)
    body = "".join(kept).strip("\n")
    new = ("# My Claude Code instructions\n\n<!-- Team rules now live in ~/.claude/rules/ap-optimal-claude.md "
           "(kept current by the plugin). Add your own instructions here. -->\n")
    if body:
        new += "\n" + body + "\n"
    path.write_text(new, encoding="utf-8")
    notes.append(f"~/.claude/CLAUDE.md: team sections moved to the managed rules file; kept {len(kept)} personal section(s); backup in ~/.claude/backups/")


def remove_duplicate_skills(claude_dir: Path, legacy: dict, notes: list) -> None:
    for name, digests in legacy.get("skill_sha256", {}).items():
        skill_dir = claude_dir / "skills" / name
        candidates = [skill_dir / "SKILL.md", skill_dir / "skill.md"]
        files = [p for p in skill_dir.iterdir()] if skill_dir.is_dir() else []
        md = next((p for p in candidates if p.exists()), None)
        if md is None or len(files) != 1:
            continue  # missing, or holds extra files a person added
        if hashlib.sha256(md.read_text(encoding="utf-8").strip().encode()).hexdigest() not in digests:
            continue  # edited by a person: keep it
        backup(skill_dir, claude_dir)
        md.unlink()
        skill_dir.rmdir()
        notes.append(f"removed duplicate skill ~/.claude/skills/{name} (old installer copy; the plugin ships the current one)")


def sync_settings(root: Path, claude_dir: Path, data_dir: Path, notes: list) -> None:
    path = claude_dir / "settings.json"
    if not path.exists():
        return
    s = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for k, v in MANAGED_SCALARS.items():
        if s.get(k) != v:
            s[k] = v
            changed = True
    baseline = json.loads((root / "settings" / "deny-baseline.json").read_text(encoding="utf-8"))
    perms = s.setdefault("permissions", {})
    deny = perms.setdefault("deny", [])
    missing = [r for r in baseline if r not in deny]
    if missing:
        deny.extend(missing)
        changed = True
        notes.append(f"added {len(missing)} safety block rule(s) to settings.json")
    marker = data_dir / MIGRATION_MARKER
    done = json.loads(marker.read_text()) if marker.exists() else {}
    if not done.get("bypass_to_auto"):
        if perms.get("defaultMode") == "bypassPermissions":
            perms["defaultMode"] = "auto"
            changed = True
            notes.append("permission mode switched once from 'bypass permissions' to 'auto' (safety check on); you can change it back with /config")
        done["bypass_to_auto"] = time.strftime("%Y-%m-%d")
        data_dir.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(done))
    if changed:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)


def run(root: Path, claude_dir: Path, data_dir: Path) -> list:
    notes = []
    legacy_file = root / "settings" / "legacy-installer.json"
    legacy = json.loads(legacy_file.read_text()) if legacy_file.exists() else {}
    for step in (lambda: migrate_claude_md(claude_dir, sync_rules(root, claude_dir, notes), legacy, notes),
                 lambda: remove_duplicate_skills(claude_dir, legacy, notes),
                 lambda: sync_settings(root, claude_dir, data_dir, notes)):
        try:
            step()
        except Exception as exc:  # fail silent per step, but say so
            notes.append(f"setup sync step skipped ({type(exc).__name__})")
    return notes


def main(argv):
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if "--plugin-root" in argv:
        root = argv[argv.index("--plugin-root") + 1]
    if not root or not Path(root, "rules", "core.md").exists():
        return 0
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    data_dir = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or claude_dir / "plugins" / "data" / "ap-optimal-claude")
    for note in run(Path(root), claude_dir, data_dir):
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
