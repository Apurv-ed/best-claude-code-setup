#!/usr/bin/env python3
"""
Claude Code Setup - One-command installer for optimized Claude Code settings.

Detects your OS (Mac/Windows/Linux) and configures:
- CLAUDE.md with battle-tested instructions for better AI coding
- settings.json with zero-prompt permissions + deny-rule guardrails + hooks
- ccx command wrapper to launch Claude Code in the configured mode
- Hook scripts for session management and git safety
- Status line showing context usage and git branch

Usage:
    Mac/Linux:  python3 claude-setup.py
    Windows:    python claude-setup.py
"""

import filecmp
import glob
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

SYSTEM = platform.system()
IS_MAC = SYSTEM == "Darwin"
IS_WINDOWS = SYSTEM == "Windows"
IS_LINUX = SYSTEM == "Linux"

HOME = os.path.expanduser("~")
CLAUDE_DIR = os.path.join(HOME, ".claude")
HOOKS_DIR = os.path.join(CLAUDE_DIR, "hooks")


# ---------------------------------------------------------------------------
# Team rules (formerly the CLAUDE.md body) and the shared skills
# ---------------------------------------------------------------------------
# Single source: the ap-optimal-claude plugin (rules/core.md, rules/platform-*.md,
# skills/). After installing the plugin, setup() runs the plugin's
# scripts/sync_setup.py, which writes ~/.claude/rules/ap-optimal-claude.md and
# migrates old installer copies. The SessionStart hook runs the same script every
# session, so rule changes reach everyone without re-running this installer.


# ---------------------------------------------------------------------------
# settings.json
# ---------------------------------------------------------------------------

def get_settings():
    settings = {
        "permissions": {
            # Auto mode: a safety classifier reviews risky actions instead of
            # prompting (Anthropic's built-in default since v2.1.283; the docs
            # reserve bypassPermissions for isolated containers/VMs). Deny rules
            # still bind in every mode (re-verified live in auto mode 2026-10-01).
            # Where auto mode is unavailable, Claude Code starts in Manual mode.
            "defaultMode": "auto",
            # The deny list replaces the old cc-wrapper blocklist, which used
            # --disallowedTools and could be shadowed.
            "deny": [
                "Bash(rm -rf:*)",
                "Bash(rm -fr:*)",
                "Bash(sudo rm:*)",
                "Bash(git push --force:*)",
                "Bash(git push -f:*)",
                "Bash(git reset --hard:*)",
                "Read(./.env)",
                "Read(./.env.*)",
                "Read(**/.env)",
                "Read(**/.env.*)",
                # Credential paths (Trail of Bits hardening pattern)
                "Read(~/.ssh/**)",
                "Read(~/.aws/**)",
                "Read(~/.kube/**)",
                "Read(~/.gnupg/**)",
                "Read(~/.npmrc)",
                "Read(~/.pypirc)"
            ]
        },
        # A compromised cloned repo could ship malicious MCP servers via its
        # .mcp.json - require explicit opt-in per project instead.
        "enableAllProjectMcpServers": False,
        "env": {
            "MAX_THINKING_TOKENS": "10000"
        },
        "autoCompactWindow": 1000000,
        "skillListingBudgetFraction": 0.02,
        # Opus for plan/think mode, Sonnet for execution - automatic smart routing.
        # Team gets stronger reasoning when planning without paying Opus rates for everything.
        # Default for NEW installs only: merge_settings keeps any model the user already chose.
        "model": "opusplan",
        # Pre-declare the team marketplace with auto-update ON and the plugin
        # enabled, so a single installer run wires up continuous updates: skills,
        # agents, and hooks (which now live in the plugin) flow to the user on
        # every restart with zero further action. The CLI install step below is
        # a belt-and-suspenders fallback for older clients.
        "extraKnownMarketplaces": {
            "apurv-ed": {
                "source": {
                    "source": "github",
                    "repo": "Apurv-ed/best-claude-code-setup"
                },
                "autoUpdate": True
            }
        },
        # Superpowers (structured planning, debugging, verification workflows) and
        # Context7 (current library docs) come from Anthropic's official plugin
        # marketplace, which auto-updates by default. Context7 needs a one-time
        # sign-in via /mcp before it answers.
        "enabledPlugins": {
            "ap-optimal-claude@apurv-ed": True,
            "superpowers@claude-plugins-official": True,
            "context7@claude-plugins-official": True
        },
        # Only the Notification hook stays here: its Windows variant is a direct
        # powershell command that fires without bash, so it cannot move into the
        # (bash-script) plugin without regressing native Windows. The other four
        # hooks now ship in the ap-optimal-claude plugin (hooks/hooks.json) so
        # they auto-update with the rest of the kit.
        "hooks": {
            "Notification": [
                {
                    "hooks": [
                        get_notification_hook()
                    ]
                }
            ]
        },
        # Status bar (model, context %, branch) via the ccstatusline npm package.
        # It needs Node.js (npx); setup() drops it on machines without npx so they
        # do not get an erroring status bar.
        "statusLine": {
            "type": "command",
            "command": "npx -y ccstatusline@2",
            "padding": 0
        }
        # opusplan: Opus for plan/think mode, Sonnet for execution - see above.
    }
    if not shutil.which("npx"):
        settings.pop("statusLine")
    return settings


# Hook scripts that moved into the ap-optimal-claude plugin (v1.1.0). When
# merging into an existing settings.json we strip any leftover registrations of
# these (from an older direct install) so they do not double-fire with the
# plugin's copies. Matched by basename anywhere in the command string.
MIGRATED_HOOK_SCRIPTS = (
    "pre-commit-check.sh", "session-start.sh",
    "pre-compact.sh", "stop-self-review.sh",
)


def _strip_migrated_hooks(hooks):
    """Drop any hook entry whose command references a now-plugin-shipped script.
    Empties (events/groups left with no hooks) are removed so the structure stays clean."""
    cleaned = {}
    for event, groups in hooks.items():
        new_groups = []
        for group in groups:
            kept = [h for h in group.get("hooks", [])
                    if not any(s in (h.get("command") or "") for s in MIGRATED_HOOK_SCRIPTS)]
            if kept:
                ng = dict(group)
                ng["hooks"] = kept
                new_groups.append(ng)
        if new_groups:
            cleaned[event] = new_groups
    return cleaned


def merge_settings(existing, managed):
    """Merge the managed baseline into an existing settings.json non-destructively.

    Preserves user customizations - theme, tui, extra hooks (RTK, pytest,
    spec-guard), other enabled plugins, and any unknown top-level keys. The
    installer owns a small set of baseline keys (env, autoCompactWindow,
    statusLine, enableAllProjectMcpServers, marketplace) and wins for those;
    deny rules and enabled plugins are UNIONED so nothing the user added is lost.
    A fresh install (existing == {}) just yields the managed baseline.
    """
    result = dict(existing)  # carry over every unknown top-level key untouched

    # Baseline keys the installer owns outright
    for key in ("enableAllProjectMcpServers", "env", "autoCompactWindow", "statusLine"):
        if key in managed:
            result[key] = managed[key]

    # model: a default for new installs only - never overwrite a model the user picked
    if "model" in managed and "model" not in result:
        result["model"] = managed["model"]

    # permissions: keep user keys (e.g. allow), enforce defaultMode, UNION the deny baseline
    perms = dict(result.get("permissions", {}))
    mperms = managed.get("permissions", {})
    if "defaultMode" in mperms:
        perms["defaultMode"] = mperms["defaultMode"]
    deny = list(perms.get("deny", []))
    for rule in mperms.get("deny", []):
        if rule not in deny:
            deny.append(rule)
    if deny:
        perms["deny"] = deny
    if perms:
        result["permissions"] = perms

    # extraKnownMarketplaces: add managed entries, keep any the user already has
    mkts = dict(result.get("extraKnownMarketplaces", {}))
    mkts.update(managed.get("extraKnownMarketplaces", {}))
    if mkts:
        result["extraKnownMarketplaces"] = mkts

    # enabledPlugins: UNION - never disable a plugin the user already enabled
    plugins = dict(result.get("enabledPlugins", {}))
    plugins.update(managed.get("enabledPlugins", {}))
    if plugins:
        result["enabledPlugins"] = plugins

    # hooks: strip the migrated-hook registrations (now in the plugin), keep every
    # other user hook (RTK, pytest, spec-guard), then set the managed Notification hook
    hooks = _strip_migrated_hooks(result.get("hooks", {}))
    for event, groups in managed.get("hooks", {}).items():
        hooks[event] = groups  # managed owns Notification
    if hooks:
        result["hooks"] = hooks

    return result


def get_notification_hook():
    if IS_MAC:
        return {
            "type": "command",
            "command": "afplay /System/Library/Sounds/Hero.aiff & open -g /Applications/Utilities/Terminal.app"
        }
    elif IS_WINDOWS:
        return {
            "type": "command",
            "command": (
                'powershell.exe -c "'
                "[System.Media.SystemSounds]::Exclamation.Play(); "
                "$null = New-BurntToastNotification "
                "-Text 'Claude Code','Needs your attention' "
                "-ErrorAction SilentlyContinue"
                '"'
            )
        }
    else:
        return {
            "type": "command",
            "command": (
                "notify-send 'Claude Code' 'Needs your attention' 2>/dev/null; "
                "printf '\\a'"
            )
        }


# ---------------------------------------------------------------------------
# Hook scripts have moved to the ap-optimal-claude plugin
# ---------------------------------------------------------------------------
# The four bash hooks (pre-commit-check, session-start, pre-compact,
# stop-self-review) now live in plugins/ap-optimal-claude/hooks/ and are
# registered via that plugin's hooks/hooks.json, so they auto-update with the
# rest of the kit. Only the OS-specific Notification hook (get_notification_hook
# above) is still installed directly into settings.json by this script, because
# its Windows variant must run without bash.


# ---------------------------------------------------------------------------
# ccx wrapper script
# ---------------------------------------------------------------------------
# NOTE: the command is deliberately NOT named "cc" - that shadows the system
# C compiler (/usr/bin/cc) and breaks native builds. Safety comes from
# permissions.deny rules in settings.json (enforced in every permission mode),
# not from a bypassable --disallowedTools blocklist.

CCX_SCRIPT_UNIX = """#!/bin/bash
claude "$@"
"""

CCX_SCRIPT_WINDOWS = """@echo off
claude %*
"""


# ---------------------------------------------------------------------------
# Installation logic
# ---------------------------------------------------------------------------

def backup_file(path):
    """Back up a file with a timestamp, but only when its contents differ from
    the most recent existing backup. The installer is meant to be re-run often
    (that is how settings changes propagate), so an unconditional copy would
    leave a growing pile of identical backups on every team member's machine -
    including a 200KB+ .claude.json copied on every no-op run."""
    if not os.path.exists(path):
        return False
    existing = sorted(glob.glob(f"{path}.backup_*"))
    if existing and filecmp.cmp(path, existing[-1], shallow=False):
        return False  # unchanged since last backup - nothing worth duplicating
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{path}.backup_{ts}"
    shutil.copy2(path, backup_path)
    print(f"  [BACKUP] {os.path.basename(path)} -> {os.path.basename(backup_path)}")
    return True


def write_file(path, content, executable=False):
    """Write content to a file, creating parent directories."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    newline = "\r\n" if path.endswith(".bat") else "\n"
    with open(path, "w", newline=newline) as f:
        f.write(content)
    if executable and not IS_WINDOWS:
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  [OK] {path}")


def merge_claude_json():
    """Merge terminal_bell setting into .claude.json without overwriting login data."""
    claude_json_path = os.path.join(HOME, ".claude.json")
    backup_file(claude_json_path)
    try:
        with open(claude_json_path, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data["preferredNotifChannel"] = "terminal_bell"
    with open(claude_json_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  [OK] {claude_json_path} (terminal bell enabled)")


def remove_legacy_cc():
    """Remove the old 'cc' wrapper that shadowed the system C compiler."""
    for legacy in [os.path.join(HOME, ".local", "bin", "cc"),
                   os.path.join(HOME, "bin", "cc.bat")]:
        if os.path.exists(legacy):
            try:
                with open(legacy) as f:
                    if "claude" in f.read():
                        os.remove(legacy)
                        print(f"  [REMOVED] legacy wrapper {legacy}")
            except OSError:
                pass
    legacy_usr = "/usr/local/bin/cc"
    if not IS_WINDOWS and os.path.exists(legacy_usr):
        try:
            with open(legacy_usr) as f:
                if "claude" in f.read():
                    print(f"  [!] Old wrapper at {legacy_usr} shadows the C compiler.")
                    print(f"      Remove it with: sudo rm {legacy_usr}")
        except OSError:
            pass


def install_ccx_wrapper():
    """Install the ccx wrapper command (user-local, no sudo, no name collision)."""
    if IS_WINDOWS:
        ccx_dir = os.path.join(HOME, "bin")
        ccx_path = os.path.join(ccx_dir, "ccx.bat")
        os.makedirs(ccx_dir, exist_ok=True)
        write_file(ccx_path, CCX_SCRIPT_WINDOWS)
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        if ccx_dir not in path_dirs:
            print(f"\n  NOTE: Add {ccx_dir} to your system PATH:")
            print(f"  1. Search 'Environment Variables' in Windows Settings")
            print(f"  2. Edit PATH, add: {ccx_dir}")
            print(f"  3. Restart your terminal")
    else:
        ccx_path = os.path.join(HOME, ".local", "bin", "ccx")
        os.makedirs(os.path.dirname(ccx_path), exist_ok=True)
        write_file(ccx_path, CCX_SCRIPT_UNIX, executable=True)
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        if os.path.dirname(ccx_path) not in path_dirs:
            print(f"  NOTE: Add {os.path.dirname(ccx_path)} to your PATH, e.g.:")
            print(f"  echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.zshrc")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_plugin_sync():
    """Run the installed plugin's sync_setup.py (team rules, migrations, deny rules).

    Same script the SessionStart hook runs every session, so the installer and the
    plugin share one implementation. Returns True when it ran.
    """
    pattern = os.path.join(CLAUDE_DIR, "plugins", "cache", "*", "ap-optimal-claude", "*", "scripts", "sync_setup.py")
    found = sorted(glob.glob(pattern), key=os.path.getmtime)
    if not found:
        print("  [SKIP] plugin not installed yet - the team rules arrive at your first session start.")
        return False
    script = found[-1]
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=os.path.dirname(os.path.dirname(script)))
    try:
        r = subprocess.run([sys.executable, script], capture_output=True, text=True, env=env, timeout=60)
        for line in (r.stdout or "").splitlines():
            print(f"  [OK] {line}")
        print(f"  [OK] team rules: {os.path.join(CLAUDE_DIR, 'rules', 'ap-optimal-claude.md')}")
        return True
    except Exception as exc:
        print(f"  [!] setup sync failed ({exc}) - it retries at your next session start.")
        return False


def install_team_plugin():
    """Belt-and-suspenders plugin install via the claude CLI.

    settings.json already pre-declares the marketplace (auto-update ON) and
    enables the plugin via extraKnownMarketplaces + enabledPlugins, so on most
    clients the plugin installs and stays current with no CLI step. This runs
    the explicit CLI commands anyway to cover older clients that do not act on
    those settings keys.
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        print("  [SKIP] claude CLI not on PATH - settings.json already enables the")
        print("         plugin, so it should install on restart. If it does not, run:")
        print("         /plugin marketplace add Apurv-ed/best-claude-code-setup")
        print("         /plugin install ap-optimal-claude@apurv-ed")
        return
    steps = [
        (["plugin", "marketplace", "add", "Apurv-ed/best-claude-code-setup"],
         "marketplace apurv-ed"),
        (["plugin", "install", "ap-optimal-claude@apurv-ed"],
         "plugin ap-optimal-claude"),
        # Anthropic's official marketplace: registered on a first interactive
        # session, but a fresh machine may not have it yet.
        (["plugin", "marketplace", "add", "anthropics/claude-plugins-official"],
         "marketplace claude-plugins-official"),
        (["plugin", "install", "superpowers@claude-plugins-official"],
         "plugin superpowers"),
        (["plugin", "install", "context7@claude-plugins-official"],
         "plugin context7 (sign in once with /mcp to use it)"),
    ]
    for args, label in steps:
        try:
            r = subprocess.run([claude_bin] + args, capture_output=True, text=True, timeout=180)
            out = (r.stdout or r.stderr or "").strip()
            tail = out.splitlines()[-1] if out else "done"
            print(f"  [{'OK' if r.returncode == 0 else '!'}] {label}: {tail}")
            if r.returncode != 0:
                print("      If this keeps failing, run inside Claude Code: /plugin install ap-optimal-claude@apurv-ed")
        except Exception as exc:
            print(f"  [!] {label} failed ({exc})")
            print("      Run inside Claude Code: /plugin install ap-optimal-claude@apurv-ed")


def setup():
    plat_name = "Mac" if IS_MAC else "Windows" if IS_WINDOWS else "Linux"
    print(f"\nClaude Code Setup - {plat_name}")
    print("=" * 50)

    # Create directories
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    os.makedirs(HOOKS_DIR, exist_ok=True)

    # Back up existing files
    print("\n1. Backing up existing files...")
    backed_up = False
    for fname in ["CLAUDE.md", "settings.json"]:
        if backup_file(os.path.join(CLAUDE_DIR, fname)):
            backed_up = True
    if not backed_up:
        print("  No existing files to back up.")

    # The team rules no longer go into ~/.claude/CLAUDE.md (which now belongs to the
    # user): the plugin writes ~/.claude/rules/ap-optimal-claude.md in step 8.
    print("\n2. Your ~/.claude/CLAUDE.md is left for your own instructions (team rules come from the plugin).")

    # Write settings.json - MERGE into any existing file (a timestamped backup was
    # made above). Overwriting wholesale would wipe user customizations: other
    # enabled plugins, theme/tui, and extra hooks (RTK, pytest, spec-guard).
    print("\n3. Installing settings.json (merging into existing)...")
    managed = get_settings()
    settings_path = os.path.join(CLAUDE_DIR, "settings.json")
    try:
        with open(settings_path) as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {}
    settings = merge_settings(existing, managed)
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"  [OK] {settings_path}")

    # Hooks now ship in the ap-optimal-claude plugin (hooks/hooks.json) so they
    # auto-update with the rest of the kit. Remove the copies that older installs
    # wrote into ~/.claude/hooks: leaving them would double-fire every hook once
    # the plugin updates (plugin + settings.json would both register them). The
    # Notification hook stays inline in settings.json and needs no script file.
    print("\n4. Migrating hooks to the plugin (removing old local copies)...")
    migrated_hooks = [
        "pre-commit-check.sh", "session-start.sh",
        "pre-compact.sh", "stop-self-review.sh",
        # afk-resume.sh: retired reminder loop from earlier versions (token sink -
        # each wakeup re-read the whole conversation at cold-cache prices).
        "afk-resume.sh",
    ]
    removed_any = False
    for hname in migrated_hooks:
        hpath = os.path.join(HOOKS_DIR, hname)
        if os.path.exists(hpath):
            os.remove(hpath)
            print(f"  [REMOVED] {hname}")
            removed_any = True
    if not removed_any:
        print("  Clean install - nothing to migrate.")

    # Skills (startup, update-github, project-docs, save-transcription, grill-me, ...)
    # ship only in the plugin now. Old installer copies in ~/.claude/skills are removed
    # by the plugin's sync_setup.py in step 8, and only when byte-identical to a copy
    # some installer version wrote, so a skill a person edited is never touched.

    # Remove the dead .claudeignore (not a Claude Code feature; replaced by
    # permissions.deny Read rules in settings.json)
    claudeignore_path = os.path.join(HOME, ".claudeignore")
    if os.path.exists(claudeignore_path):
        os.remove(claudeignore_path)
        print(f"\n  [REMOVED] {claudeignore_path} (.claudeignore is not a Claude Code feature)")

    # Merge terminal bell setting
    print("\n5. Configuring notifications...")
    merge_claude_json()

    # Install ccx wrapper (and clean up the old cc one)
    print("\n6. Installing ccx command...")
    remove_legacy_cc()
    install_ccx_wrapper()

    # Install the team plugin (marketplace + ap-optimal-claude) - no typed commands needed
    print("\n7. Installing the ap-optimal-claude team plugin...")
    install_team_plugin()

    print("\n8. Applying team rules and migrations from the plugin...")
    run_plugin_sync()

    # Self-copy: save installer to ~/.claude/claude-setup.py so the update
    # notification (injected by the session-start hook) always has a valid path
    # to give the user, regardless of where they originally ran this from.
    try:
        self_dst = os.path.join(CLAUDE_DIR, "claude-setup.py")
        if os.path.abspath(__file__) != os.path.abspath(self_dst):
            shutil.copy2(__file__, self_dst)
        # Version file read by the session-start hook to detect outdated installs
        with open(os.path.join(CLAUDE_DIR, ".installer_version"), "w") as vf:
            vf.write("1\n")
        print("  [OK] Saved installer to ~/.claude/claude-setup.py")
    except Exception as e:
        print(f"  [!] Could not self-copy installer: {e}")

    # Done
    print("\n" + "=" * 50)
    print("Setup complete!")
    print("=" * 50)

    print(f"\nPlatform:       {plat_name}")
    print(f"Team rules:     {os.path.join(CLAUDE_DIR, 'rules', 'ap-optimal-claude.md')} (kept current by the plugin)")
    print(f"Your rules:     {os.path.join(CLAUDE_DIR, 'CLAUDE.md')} and other files in {os.path.join(CLAUDE_DIR, 'rules')}")
    print(f"settings.json:  {os.path.join(CLAUDE_DIR, 'settings.json')}")
    print(f"Skills, hooks:  via the ap-optimal-claude plugin (auto-updating)")

    print("\n--- Continuous updates (auto-configured) ---")
    print("  The plugin's marketplace is registered with auto-update ON. Skills, agents,")
    print("  hooks, the team rules and new safety blocks arrive automatically: downloaded")
    print("  during one session, active from the next. You should not need to re-run this.")

    print("\n--- Token optimization (auto-configured) ---")
    print("  MAX_THINKING_TOKENS=10000     (caps the extended-thinking budget)")

    print("  Stop hook (via plugin)         (self-review pass when code was edited)")

    print("\n--- How to use ---")
    print("  ccx             Start Claude Code (auto mode + deny-rule guardrails)")
    print("  ccx --resume    Resume your last session")
    print("  claude          Same thing (settings.json sets the permission mode)")

    print("\n--- Plugins ---")
    print("  Installed for you: superpowers (structured workflows), context7 (latest library docs;")
    print("  sign in once with /mcp). Optional, inside a Claude session:")
    print("  /plugin install code-simplifier@claude-plugins-official   (code quality reviews)")

    if IS_MAC:
        print("\n--- Mac notifications ---")
        print("  When Claude needs attention you get a chime + the Terminal dock badge.")
        print("  No floating banners are used.")

    if IS_WINDOWS:
        print("\n--- Windows notification setup ---")
        print("  For richer notifications, install BurntToast:")
        print("  powershell: Install-Module -Name BurntToast")

    print("\n--- Safety guardrails (permissions.deny in settings.json) ---")
    print("  rm -rf / rm -fr / sudo rm   (recursive deletion)")
    print("  git push --force / -f       (overwriting remote history)")
    print("  Read .env / .env.*          (secrets stay out of context)")
    print("  These are hard blocks in every permission mode (verified live).")
    print("  Default mode is 'auto': a safety check stops other risky actions")
    print("  (wiping unsaved work, running downloaded scripts) without asking you each time.\n")


if __name__ == "__main__":
    setup()
