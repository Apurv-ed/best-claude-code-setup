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
   ONCE switch defaultMode bypassPermissions -> auto (a later choice is respected), and
   replace the old installer's Windows notification command (byte-exact match only), which
   Git Bash broke by expanding its "$null", and its Mac one, which opened Terminal even in
   desktop app sessions. Keep auto-update on for this setup's marketplace:
   `claude plugin marketplace add` drops the key, and third-party marketplaces default to off
   (an explicit "off", in settings or under /plugin, is respected). The same for the own-name
   marketplace once the setup comes from there. Add FORCE_AUTOUPDATE_PLUGINS=1 to env when
   missing, so plugin updates still arrive where Claude Code's own updater is off.
5. Status line: copy scripts/context_meter.py to ~/.claude/scripts/ap-context-meter.py and,
   only when the status line is still the setup's default, wrap it so the context-size hook
   can read the window numbers. ccstatusline (exact version BAR_VERSION) is installed into
   ~/.claude/ccstatusline in the background and, once there, run with node directly: "npx -y"
   re-resolved the package on every refresh (~1 s of CPU each, ~0.2 s direct). Until then, or
   if the install fails (retried once a day), npx stays. A personal status line is never touched.

Usage: python3 sync_setup.py   (needs CLAUDE_PLUGIN_ROOT, or pass --plugin-root DIR)
"""
import hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

MANAGED_SCALARS = {"skillListingBudgetFraction": 0.02}
SUBAGENT_DEFAULT_MODEL = "sonnet"
SUBAGENT_DEFAULT_MIN_VERSION = (2, 1, 251)  # from here the variable is only a fallback
RULES_NAME = "ap-optimal-claude.md"
RULES_HEADER = ("<!-- Managed by the ap-optimal-claude plugin (v{version}): refreshed every session, edits here are overwritten.\n"
                "     Put personal rules in another file in this folder. -->\n# Claude Code Instructions (team rules)\n\n")
RULES_VERSION = re.compile(r"ap-optimal-claude plugin \(v(\d+(?:\.\d+)*)\)")
MIGRATION_MARKER = "migrations.json"
DEFAULT_STATUSLINE = "npx -y ccstatusline@2"  # what claude-setup.py installs
BAR_VERSION = "2.2.32"  # exact pin: a plugin release that changes it reinstalls the bar
BAR_DIR = "ccstatusline"  # under the claude dir, so no global npm write or sudo is needed
BAR_SCRIPT = ("node_modules", "ccstatusline", "dist", "ccstatusline.js")
BAR_RETRY_SECONDS = 86400
METER_NAME = "ap-context-meter.py"
# This setup's marketplace. `claude plugin marketplace add` rewrites its settings entry without
# autoUpdate, and third-party marketplaces default to auto-update OFF, so the sync puts it back.
MARKETPLACE = "apurv-ed"
MARKETPLACE_REPO = "Apurv-ed/best-claude-code-setup"
# The maintained own-name marketplace every copy moves to (scripts/self_update.py); once a
# person is on it, its entry needs the same auto-update care.
OWN_MARKETPLACE = "apurv-ed"
OWN_MARKETPLACE_REPO = "Apurv-ed/best-claude-code-setup"
PLUGIN_NAME = "ap-optimal-claude"
# Plugins update even where Claude Code's own updater is switched off (DISABLE_AUTOUPDATER and
# similar); added only when the person has not set it themselves.
MANAGED_ENV = {"FORCE_AUTOUPDATE_PLUGINS": "1"}
# Windows notification hook: the old installer's command, and the fix (must equal
# claude-setup.py get_notification_hook() on Windows; tested in test_windows_compat.py).
WIN_NOTIFY_OLD = ('powershell.exe -c "[System.Media.SystemSounds]::Exclamation.Play(); $null = New-BurntToastNotification '
                  "-Text 'Claude Code','Needs your attention' -ErrorAction SilentlyContinue\"")
WIN_NOTIFY_NEW = ('powershell.exe -c "[System.Media.SystemSounds]::Exclamation.Play(); New-BurntToastNotification '
                  "-Text 'Claude Code','Needs your attention' -ErrorAction SilentlyContinue | Out-Null\"")
# Mac notification hook: the old command also opened Terminal in desktop-app and IDE sessions;
# the new one (must equal claude-setup.py get_notification_hook() on Mac) only in terminal sessions.
MAC_NOTIFY_OLD = "afplay /System/Library/Sounds/Hero.aiff & open -g /Applications/Utilities/Terminal.app"
MAC_NOTIFY_NEW = ("afplay /System/Library/Sounds/Hero.aiff & "
                  'case "$CLAUDE_CODE_ENTRYPOINT" in ""|cli) open -g /Applications/Utilities/Terminal.app;; esac')
NOTIFY_REPAIRS = {
    WIN_NOTIFY_OLD: (WIN_NOTIFY_NEW, "repaired the Windows 'Claude needs you' notification sound"),
    MAC_NOTIFY_OLD: (MAC_NOTIFY_NEW, "the 'Claude needs you' sound no longer opens Terminal in desktop app sessions"),
}


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


def version_tuple(text):
    try:
        return tuple(int(p) for p in text.split("."))
    except (AttributeError, ValueError):
        return None


def plugin_version(root: Path):
    try:
        return json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version", "0")
    except (OSError, ValueError):
        return "0"


def sync_rules(root: Path, claude_dir: Path, notes: list) -> set:
    core = (root / "rules" / "core.md").read_text(encoding="utf-8")
    plat = (root / "rules" / f"platform-{platform_name()}.md").read_text(encoding="utf-8")
    version = plugin_version(root)
    content = RULES_HEADER.format(version=version) + plat.rstrip("\n") + "\n\n" + core
    target = claude_dir / "rules" / RULES_NAME
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    stamp = RULES_VERSION.search(existing[:300])
    written_by = version_tuple(stamp.group(1)) if stamp else None
    if written_by and (version_tuple(version) or ()) < written_by:
        # a session still running an older plugin version: never roll newer rules back
        return {h.strip() for h in re.findall(r"(?m)^## .+$", existing)}
    if existing != content:
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


def claude_version():
    """Installed Claude Code version as a tuple, or None when it cannot be read."""
    exe = shutil.which("claude")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in m.groups()) if m else None


def default_subagent_model(s: dict, done: dict, notes: list) -> bool:
    """Once: helpers that get no model of their own run on Sonnet, not the session model (ADR-0070).

    Before 2.1.251 the variable overrode agent files too (would drop the Opus checkers), so older
    versions are retried later. A Haiku main model or a value the person set is left alone for good."""
    env = s.get("env") if isinstance(s.get("env"), dict) else {}
    if "CLAUDE_CODE_SUBAGENT_MODEL" in env or "haiku" in str(s.get("model", "")):
        done["subagent_model_default"] = "skipped " + time.strftime("%Y-%m-%d")
        return False
    version = claude_version()
    if version is None or version < SUBAGENT_DEFAULT_MIN_VERSION:
        return False  # not marked done: tried again next session, after an update
    s["env"] = {**env, "CLAUDE_CODE_SUBAGENT_MODEL": SUBAGENT_DEFAULT_MODEL}
    done["subagent_model_default"] = time.strftime("%Y-%m-%d")
    notes.append("helper agents now default to Sonnet instead of your main model (saves plan usage; "
                 "checkers that need Opus still use it). To undo, delete CLAUDE_CODE_SUBAGENT_MODEL in settings.json")
    return True


def auto_update_turned_off(claude_dir: Path, marketplace: str = MARKETPLACE) -> bool:
    """True when /plugin says auto-update is off for this marketplace, or the file can't be read."""
    known_file = claude_dir / "plugins" / "known_marketplaces.json"
    if not known_file.exists():
        return False
    try:
        known = json.loads(known_file.read_text(encoding="utf-8"))
        entry = known.get(marketplace) if isinstance(known, dict) else None
        return isinstance(entry, dict) and entry.get("autoUpdate") is False
    except Exception:
        return True  # unreadable: leave the person's setup as it is


def keep_auto_update(s: dict, claude_dir: Path, notes: list) -> bool:
    """Make sure this setup's marketplace auto-updates, unless the person turned it off.

    Covers this copy's marketplace (declared when missing) and the own-name marketplace once
    the person is on it. Never raises: an odd settings file must not cost the other settings
    steps (deny rules)."""
    targets = {MARKETPLACE: MARKETPLACE_REPO}
    try:
        markets = s.get("extraKnownMarketplaces")
        enabled = s.get("enabledPlugins") if isinstance(s.get("enabledPlugins"), dict) else {}
        if enabled.get(f"{PLUGIN_NAME}@{OWN_MARKETPLACE}") or (isinstance(markets, dict) and OWN_MARKETPLACE in markets):
            targets[OWN_MARKETPLACE] = OWN_MARKETPLACE_REPO
    except Exception:
        return False
    changed = False
    for name, repo in targets.items():
        changed |= _keep_one(s, claude_dir, name, repo)
    if changed:
        notes.append("turned automatic updates for this setup back on")
    return changed


def _keep_one(s: dict, claude_dir: Path, name: str, repo: str) -> bool:
    try:
        markets = s.get("extraKnownMarketplaces")
        markets = {} if markets is None else markets
        entry = markets.get(name) if isinstance(markets, dict) else None
        if not isinstance(markets, dict) or (entry is not None and not isinstance(entry, dict)):
            return False
        if (entry and "autoUpdate" in entry) or auto_update_turned_off(claude_dir, name):
            return False
        entry = entry if entry is not None else {}
        entry.setdefault("source", {"source": "github", "repo": repo})
        entry["autoUpdate"] = True
        markets[name] = entry
        s["extraKnownMarketplaces"] = markets
    except Exception:
        return False
    return True


def managed_env(s: dict, notes: list) -> bool:
    """Add each MANAGED_ENV value the person has not set (add-only: never changes or removes theirs)."""
    env = {} if s.get("env") is None else s.get("env")
    if not isinstance(env, dict):
        return False  # not a valid env block: leave what the person wrote alone
    missing = {k: v for k, v in MANAGED_ENV.items() if k not in env}
    if not missing:
        return False
    s["env"] = {**env, **missing}
    notes.append("setup fixes now arrive even where Claude Code's own updater is switched off")
    return True


def read_migrations(marker: Path) -> dict:
    """The record of one-time migrations already done; unreadable or not an object counts as none."""
    try:
        done = json.loads(marker.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return done if isinstance(done, dict) else {}


def sync_settings(root: Path, claude_dir: Path, data_dir: Path, notes: list) -> None:
    path = claude_dir / "settings.json"
    if not path.exists():
        return
    s = json.loads(path.read_text(encoding="utf-8-sig"))  # Windows PowerShell 5.1 writes a BOM
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
    for group in (s.get("hooks") or {}).get("Notification") or []:
        for hook in (group.get("hooks") or []) if isinstance(group, dict) else []:
            if isinstance(hook, dict) and hook.get("command") in NOTIFY_REPAIRS:
                hook["command"], note = NOTIFY_REPAIRS[hook["command"]]
                changed = True
                notes.append(note)
    marker = data_dir / MIGRATION_MARKER
    done = read_migrations(marker)
    if not done.get("bypass_to_auto"):
        if perms.get("defaultMode") == "bypassPermissions":
            perms["defaultMode"] = "auto"
            changed = True
            notes.append("permission mode switched once from 'bypass permissions' to 'auto' (safety check on); you can change it back with /config")
        done["bypass_to_auto"] = time.strftime("%Y-%m-%d")
        data_dir.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(done))
    if not done.get("subagent_model_default"):
        changed |= default_subagent_model(s, done, notes)
        if done.get("subagent_model_default"):
            data_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps(done))
    changed |= keep_auto_update(s, claude_dir, notes)
    changed |= managed_env(s, notes)
    if changed:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)


def install_bar(prefix: Path) -> None:
    """Start npm installing the pinned status bar into prefix, in the background.

    Never waits: offline, npm retries for over a minute and the session start must not.
    The next sync picks the bar up once it is there. Raises if npm cannot be started."""
    npm = shutil.which("npm")
    if not npm:
        raise FileNotFoundError("npm")
    detach = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
              if os.name == "nt" else {"start_new_session": True})
    subprocess.Popen([npm, "install", "--prefix", str(prefix), f"ccstatusline@{BAR_VERSION}", "--ignore-scripts",
                      "--no-audit", "--no-fund", "--silent"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **detach)


def installed_bar_version(claude_dir: Path):
    try:
        pkg = claude_dir.joinpath(BAR_DIR, "node_modules", "ccstatusline", "package.json")
        return json.loads(pkg.read_text(encoding="utf-8")).get("version")
    except Exception:
        return None


def local_bar(claude_dir: Path, data_dir: Path):
    """Command that runs the installed ccstatusline with node, or None (then npx stays).

    Starts a background install when the pinned version is missing, at most once a day."""
    node = shutil.which("node")
    if not node or "'" in node + str(claude_dir):  # the wrapper passes the command in single quotes
        return None
    script = claude_dir.joinpath(BAR_DIR, *BAR_SCRIPT)
    if installed_bar_version(claude_dir) != BAR_VERSION or not script.exists():
        marker = data_dir / "ccstatusline-install-tried"
        if not marker.exists() or time.time() - marker.stat().st_mtime >= BAR_RETRY_SECONDS:
            data_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text("1")
            try:
                install_bar(claude_dir / BAR_DIR)
            except Exception:
                pass
    return f'"{node}" "{script}"' if script.exists() else None


def wrap(python: str, meter: Path, bar: str) -> str:
    # If python cannot start, the shell falls back to the plain status bar.
    return f'"{python}" "{meter}" statusline \'{bar}\' || {bar}'


def setup_statusline_kind(command, meter: Path, script: Path):
    """'npx' or 'direct' when command is one of the forms this sync writes, else None.

    Exact forms only, so a personal status line that reuses the meter is never touched."""
    if command == DEFAULT_STATUSLINE:
        return "npx"
    if not isinstance(command, str):
        return None
    py, m = r'"[^"]+"', re.escape(f'"{meter}"')
    npx = re.escape(DEFAULT_STATUSLINE)
    if re.fullmatch(f'{py} {m} statusline (?:"{npx}"|\'{npx}\') \\|\\| {npx}', command):
        return "npx"
    direct = f'{py} {re.escape(chr(34) + str(script) + chr(34))}'
    if re.fullmatch(f"{py} {m} statusline '{direct}' \\|\\| {direct}", command):
        return "direct"
    return None


def sync_statusline(root: Path, claude_dir: Path, notes: list, data_dir: Path = None) -> None:
    path = claude_dir / "settings.json"
    if not path.exists():
        return
    src = root / "scripts" / "context_meter.py"
    dest = claude_dir / "scripts" / METER_NAME
    if not dest.exists() or dest.read_bytes() != src.read_bytes():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    s = json.loads(path.read_text(encoding="utf-8-sig"))  # Windows PowerShell 5.1 writes a BOM
    line = s.get("statusLine")
    # On Windows "python3" can be the Microsoft Store placeholder; this script runs under a
    # Python the hook has checked, so use that one there.
    python = sys.executable if platform_name() == "windows" else shutil.which("python3") or shutil.which("python")
    if not isinstance(line, dict) or not python:
        return
    old = line.get("command")
    script = claude_dir.joinpath(BAR_DIR, *BAR_SCRIPT)
    kind = setup_statusline_kind(old, dest, script)
    if not kind:
        return
    bar = local_bar(claude_dir, data_dir or claude_dir / "plugins" / "data" / "ap-optimal-claude")
    if not bar and kind == "direct" and script.exists():
        return  # node not found in this shell only: keep the bar that works in normal sessions
    wanted = wrap(python, dest, bar or DEFAULT_STATUSLINE)
    if old == wanted:
        return
    line["command"] = wanted
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    if old == DEFAULT_STATUSLINE:
        notes.append("status bar now also lets Claude suggest a fresh start once a conversation passes 40% full")
    if bar and kind == "npx":
        notes.append("status bar now runs an installed ccstatusline instead of npx (about 5x less CPU per refresh)")


def run(root: Path, claude_dir: Path, data_dir: Path) -> list:
    notes = []
    legacy_file = root / "settings" / "legacy-installer.json"
    legacy = json.loads(legacy_file.read_text()) if legacy_file.exists() else {}
    for step in (lambda: migrate_claude_md(claude_dir, sync_rules(root, claude_dir, notes), legacy, notes),
                 lambda: remove_duplicate_skills(claude_dir, legacy, notes),
                 lambda: sync_settings(root, claude_dir, data_dir, notes),
                 lambda: sync_statusline(root, claude_dir, notes, data_dir)):
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
