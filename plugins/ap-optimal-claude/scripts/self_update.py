#!/usr/bin/env python3
"""Keep the plugin itself current, once a day, without the person doing anything.

Claude Code's own plugin auto-update is unreliable for this setup (third-party marketplaces
default to off, `marketplace add` drops the setting, it skips short and `-p` sessions, and
several env switches turn it off). `claude plugin marketplace update <mkt>` followed by
`claude plugin update <plugin>@<mkt>` always works and needs no login, so this runs exactly that.

Two parts:
- `check` (run by the SessionStart hook, fast, never calls the CLI): turns the last job's
  result into notes for Claude (a version change, a finished move, or 3 failed days in a row,
  each said once), then starts `run` as a detached background job when 24 h have passed since
  the last start. Only a copy installed from its marketplace (in the plugin cache) does this.
- `run` (the background job): updates this copy from its marketplace. A copy from any other
  marketplace than the own-name one then moves the person to it: add that marketplace, install
  the plugin from it, copy the data folder files the new copy lacks, keep its auto-update on,
  and switch enabledPlugins over (re-reading settings.json, which the CLI rewrites). Any failure
  leaves enabledPlugins alone and the next day tries again. The own-name copy turns other
  copies of the setup off (with two enabled, only one runs its hooks and every skill loads twice).

Usage: python3 self_update.py check | run   (needs CLAUDE_PLUGIN_ROOT; data in CLAUDE_PLUGIN_DATA)
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_setup import MARKETPLACE, MARKETPLACE_REPO, OWN_MARKETPLACE, OWN_MARKETPLACE_REPO, PLUGIN_NAME  # noqa: E402

STATE = "self-update.json"
LOG = "self-update.log"
MOVED_MARK = "self-update-moved"  # left in the new copy's data folder; its next session says so once
LOCK = "self-update.lock"  # only one job at a time (two sessions can start together)
OWN_OFF_MARK = "self-update-own-off-noted"  # the person turned the own-name copy off: logged once
NOT_COPIED = {STATE, LOG, MOVED_MARK, LOCK, OWN_OFF_MARK}
LOCK_STALE = 1800  # a lock older than 30 minutes was left by a job that died
INTERVAL = 86400
CMD_TIMEOUT = 180  # each CLI call; a git fetch on a slow line can take a while
FAIL_DAYS = 3
LOG_MAX = 200_000
SITE = "https://apurv.org/best-claude-code-settings/"
UPDATED_NOTE = "Your setup was updated to {}; it is active in new sessions."
MOVE_NOTE = (f"Your setup now comes from {SITE} (the copy that is kept up to date). "
             "Nothing for you to do: this session already uses it.")
FAIL_NOTE = ("Your setup could not update itself for 3 days in a row (often no internet at the time). "
             "It keeps trying once a day; nothing to do unless this message keeps coming back.")


# ---------- small file helpers (all fail soft) ----------

def read_json(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))  # Windows PowerShell 5.1 writes a BOM
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def num(value) -> float:
    """A number from the state file; anything else (text, true/false, null) counts as 0."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def day_of(when: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(when))


def take_lock(data_dir: Path) -> bool:
    """Create the lock file atomically; False when another job holds a fresh one."""
    path = data_dir / LOCK
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime < LOCK_STALE:
                    return False
                path.unlink()  # stale: its job died; take it over
            except FileNotFoundError:
                pass  # released meanwhile: try again
            except OSError:
                return False
        except OSError:
            return False
    return False


def release_lock(data_dir: Path) -> None:
    try:
        (data_dir / LOCK).unlink()
    except OSError:
        pass


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def log(data_dir: Path, line: str) -> None:
    try:
        path = data_dir / LOG
        if path.exists() and path.stat().st_size > LOG_MAX:
            path.write_text(path.read_text(encoding="utf-8", errors="replace")[-LOG_MAX // 2:], encoding="utf-8")
        with open(path, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
    except Exception:
        pass


def installed_version(claude_dir: Path, key: str):
    """Version of plugin `key` installed at user scope, or None."""
    data = read_json(claude_dir / "plugins" / "installed_plugins.json", {})
    entries = (data.get("plugins") or {}).get(key) if isinstance(data.get("plugins"), dict) else None
    for e in entries if isinstance(entries, list) else []:
        if isinstance(e, dict) and e.get("scope", "user") == "user":
            return e.get("version") or "unknown"
    return None


def is_installed_copy(root: Path, claude_dir: Path) -> bool:
    """True when this code runs from the plugin cache of its own marketplace (not a dev folder)."""
    try:
        cache = os.path.normcase(os.path.realpath(claude_dir / "plugins" / "cache" / MARKETPLACE))
        here = os.path.normcase(os.path.realpath(root))
        return os.path.commonpath([cache, here]) == cache
    except Exception:
        return False


# ---------- check: session start ----------

def spawn_job(claude_dir: Path, data_dir: Path) -> None:
    """Start `run` fully detached, output to the log, so the session start never waits."""
    data_dir.mkdir(parents=True, exist_ok=True)
    out = open(data_dir / LOG, "a", encoding="utf-8")
    args = [sys.executable, str(Path(__file__).resolve()), "run", "--claude-dir", str(claude_dir), "--data-dir", str(data_dir)]
    common = dict(stdin=subprocess.DEVNULL, stdout=out, stderr=out, close_fds=True)
    try:
        if os.name == "nt":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            try:  # outlive the hook even if Claude Code runs hooks in a job object
                subprocess.Popen(args, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **common)
            except OSError:
                subprocess.Popen(args, creationflags=flags, **common)
        else:
            subprocess.Popen(args, start_new_session=True, **common)
    finally:
        out.close()


def check(root: Path, claude_dir: Path, data_dir: Path, now=None, spawn=spawn_job) -> list:
    now = time.time() if now is None else now
    notes = []
    state = read_json(data_dir / STATE, {})
    before = dict(state)
    moved = data_dir / MOVED_MARK
    if moved.exists():
        notes.append(MOVE_NOTE)
        try:
            moved.unlink()
        except OSError:
            pass
    pending = state.pop("pending_version", None)
    if isinstance(pending, str) and pending:
        notes.append(UPDATED_NOTE.format(pending))
    if num(state.get("fail_streak")) >= FAIL_DAYS and state.get("fail_noted") is not True:
        notes.append(f"{FAIL_NOTE} (log: {data_dir / LOG})")
        state["fail_noted"] = True
    last = state.get("last_start", 0)
    due = not isinstance(last, (int, float)) or now - last >= INTERVAL or last > now + 3600
    start = due and is_installed_copy(root, claude_dir)
    if start:
        state["last_start"] = now
    if state != before:
        write_json(data_dir / STATE, state)
    if start:
        spawn(claude_dir, data_dir)
    return notes


# ---------- run: the background job ----------

def find_cli():
    """$CLAUDE_CODE_EXECPATH when it names a file (desktop app sessions may have no claude on
    PATH), else claude on PATH (claude.cmd or claude.exe on Windows via PATHEXT)."""
    exe = os.environ.get("CLAUDE_CODE_EXECPATH", "")
    if exe and os.path.isfile(exe):
        return exe
    return shutil.which("claude")


def cli(exe: str, data_dir: Path, *args) -> bool:
    extra = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        r = subprocess.run([exe, *args], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=CMD_TIMEOUT, **extra)
        tail = " | ".join((r.stdout + r.stderr).strip().splitlines()[-3:])
        log(data_dir, f"claude {' '.join(args)} -> {r.returncode} {tail}")
        return r.returncode == 0
    except Exception as exc:
        log(data_dir, f"claude {' '.join(args)} -> {type(exc).__name__}")
        return False


def edit_settings(claude_dir: Path, change) -> bool:
    """Re-read settings.json (the CLI rewrites it), apply change(s) -> bool, write only if changed."""
    path = claude_dir / "settings.json"
    s = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(s, dict) or not change(s):
        return False
    write_json(path, s)
    return True


def turn_off_other_copies(s: dict, keep: str) -> bool:
    enabled = s.get("enabledPlugins")
    if not isinstance(enabled, dict):
        return False
    off = [k for k, v in enabled.items() if k.startswith(PLUGIN_NAME + "@") and k != keep and v is not False]
    for k in off:
        enabled[k] = False
    return bool(off)


def switch_to_own(s: dict) -> bool:
    """Own-name copy on with auto-update, every other copy of the setup off."""
    key = f"{PLUGIN_NAME}@{OWN_MARKETPLACE}"
    markets = s.get("extraKnownMarketplaces")
    markets = {} if markets is None else markets
    if not isinstance(markets, dict):
        raise ValueError("extraKnownMarketplaces is not an object")
    enabled = s.get("enabledPlugins")
    enabled = {} if enabled is None else enabled
    if not isinstance(enabled, dict):
        raise ValueError("enabledPlugins is not an object")
    changed = False
    entry = markets.get(OWN_MARKETPLACE) if isinstance(markets.get(OWN_MARKETPLACE), dict) else {}
    if entry.get("autoUpdate") is not True or "source" not in entry:
        entry.setdefault("source", {"source": "github", "repo": OWN_MARKETPLACE_REPO})
        entry["autoUpdate"] = True
        markets[OWN_MARKETPLACE] = entry
        s["extraKnownMarketplaces"] = markets
        changed = True
    if enabled.get(key) is not True:
        enabled[key] = True
        changed = True
    s["enabledPlugins"] = enabled
    return turn_off_other_copies(s, key) or changed


def restore_entry(s: dict, key: str, before: dict) -> bool:
    """Put enabledPlugins[key] back to its value in `before` (removed if it was not there)."""
    enabled = s.get("enabledPlugins")
    if not isinstance(enabled, dict) or enabled.get(key) == before.get(key):
        return False
    if key in before:
        enabled[key] = before[key]
    else:
        enabled.pop(key, None)
    return True


def copy_data(src: Path, dest: Path) -> None:
    """Copy the files the new copy's data folder lacks (migrations.json etc.); never overwrite."""
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if not p.is_file() or rel.parts[0] in NOT_COPIED or p.name.endswith(".tmp"):
            continue
        target = dest / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)


def version_tuple(v):
    """(1, 11, 0) from "1.11.0"; "1.10" pads to (1, 10, 0). A suffix such as "-beta" is
    ignored; None when it does not start with numbers."""
    try:
        core = re.split(r"[^0-9.]", str(v).strip(), maxsplit=1)[0]
        parts = [int(x) for x in core.split(".") if x != ""]
    except (TypeError, ValueError):
        return None
    if not parts:
        return None
    return tuple(parts + [0] * (3 - len(parts)))


def older(candidate, running) -> bool:
    """True only when both versions are known and candidate is lower."""
    a, b = version_tuple(candidate), version_tuple(running)
    return a is not None and b is not None and a < b


def offered_version(claude_dir: Path):
    """The version the own-name marketplace offers, read from its local copy; None if unknown."""
    try:
        entry = read_json(claude_dir / "plugins" / "known_marketplaces.json", {}).get(OWN_MARKETPLACE)
        loc = entry.get("installLocation") if isinstance(entry, dict) else None
        base = Path(loc) if loc else claude_dir / "plugins" / "marketplaces" / OWN_MARKETPLACE
        manifest = read_json(base / ".claude-plugin" / "marketplace.json", {})
        for plugin in manifest.get("plugins") or []:
            if isinstance(plugin, dict) and plugin.get("name") == PLUGIN_NAME:
                if plugin.get("version"):
                    return plugin["version"]
                src = plugin.get("source")
                if isinstance(src, str):
                    return read_json(base / src / ".claude-plugin" / "plugin.json", {}).get("version")
    except Exception:
        pass
    return None


def own_turned_off(claude_dir: Path) -> bool:
    """True when the person set the own-name copy to false in enabledPlugins themselves."""
    enabled = read_json(claude_dir / "settings.json", {}).get("enabledPlugins")
    return isinstance(enabled, dict) and enabled.get(f"{PLUGIN_NAME}@{OWN_MARKETPLACE}") is False


def move_to_own(exe: str, claude_dir: Path, data_dir: Path, running) -> bool:
    """Move to the own-name copy, but never onto an older version than `running` (this copy's)."""
    key = f"{PLUGIN_NAME}@{OWN_MARKETPLACE}"
    if own_turned_off(claude_dir):  # respect the person's choice: no move, this copy stays on
        mark = data_dir / OWN_OFF_MARK
        if not mark.exists():
            log(data_dir, f"move: {key} was turned off on purpose in settings.json; not moving")
            try:
                mark.write_text("1", encoding="utf-8")
            except OSError:
                pass
        return True
    not_yet = f"; {key} is not turned on yet, tries again tomorrow"
    have = installed_version(claude_dir, key)
    if have is None:
        known = read_json(claude_dir / "plugins" / "known_marketplaces.json", {})
        ok = (cli(exe, data_dir, "plugin", "marketplace", "update", OWN_MARKETPLACE) if OWN_MARKETPLACE in known
              else cli(exe, data_dir, "plugin", "marketplace", "add", OWN_MARKETPLACE_REPO))
        if ok and older(offered_version(claude_dir), running):
            log(data_dir, f"move: {OWN_MARKETPLACE} offers {offered_version(claude_dir)}, older than {running}{not_yet}")
            return True
        enabled_before = read_json(claude_dir / "settings.json", {}).get("enabledPlugins")
        enabled_before = dict(enabled_before) if isinstance(enabled_before, dict) else {}
        if not ok or not cli(exe, data_dir, "plugin", "install", key) or installed_version(claude_dir, key) is None:
            log(data_dir, "move: not installed this time; settings left as they were, tries again tomorrow")
            return False
        have = installed_version(claude_dir, key)
        if older(have, running):  # installed but older: put enabledPlugins back as it was before the install
            log(data_dir, f"move: installed {have}, older than {running}{not_yet}")
            edit_settings(claude_dir, lambda s: restore_entry(s, key, enabled_before))
            return True
    elif older(have, running):  # installed earlier but behind: bring it up to date first
        if not (cli(exe, data_dir, "plugin", "marketplace", "update", OWN_MARKETPLACE)
                and cli(exe, data_dir, "plugin", "update", key)):
            return False
        have = installed_version(claude_dir, key)
        if older(have, running):
            log(data_dir, f"move: {key} is at {have}, older than {running}{not_yet}")
            return True
    target = claude_dir / "plugins" / "data" / f"{PLUGIN_NAME}-{OWN_MARKETPLACE}"
    try:
        target.mkdir(parents=True, exist_ok=True)
        copy_data(data_dir, target)
        now_enabled = read_json(claude_dir / "settings.json", {}).get("enabledPlugins")
        now_enabled = now_enabled if isinstance(now_enabled, dict) else {}
        mine_was_on = now_enabled.get(f"{PLUGIN_NAME}@{MARKETPLACE}") is True
        if edit_settings(claude_dir, switch_to_own) and mine_was_on:
            (target / MOVED_MARK).write_text("1", encoding="utf-8")
            log(data_dir, "move: done; this copy is now off")
    except Exception as exc:
        log(data_dir, f"move: settings not switched ({type(exc).__name__}); tries again tomorrow")
        return False
    return True


def run_job(claude_dir: Path, data_dir: Path, now=None) -> dict:
    data_dir.mkdir(parents=True, exist_ok=True)
    if not take_lock(data_dir):
        log(data_dir, "another update job is running; this one stops")
        return read_json(data_dir / STATE, {})
    try:
        return update(claude_dir, data_dir, time.time() if now is None else now)
    finally:
        release_lock(data_dir)


def update(claude_dir: Path, data_dir: Path, now: float) -> dict:
    key = f"{PLUGIN_NAME}@{MARKETPLACE}"
    exe = find_cli()
    before = installed_version(claude_dir, key)
    if not exe:
        log(data_dir, "claude CLI not found")
        ok = False
    elif before is None:
        log(data_dir, f"{key} is not installed for this user; nothing to update")
        ok = True
    else:
        ok = cli(exe, data_dir, "plugin", "marketplace", "update", MARKETPLACE) and cli(exe, data_dir, "plugin", "update", key)
        if MARKETPLACE != OWN_MARKETPLACE:
            ok = move_to_own(exe, claude_dir, data_dir, installed_version(claude_dir, key)) and ok
        else:
            try:
                edit_settings(claude_dir, lambda s: turn_off_other_copies(s, key))
            except Exception as exc:
                log(data_dir, f"could not turn other copies off ({type(exc).__name__})")
    after = installed_version(claude_dir, key)
    state = read_json(data_dir / STATE, {})  # re-read: a session may have started meanwhile
    state.update(finished=now, ok=ok)
    if ok:
        state.update(fail_streak=0, fail_noted=False)
        state.pop("fail_day", None)
    elif state.get("fail_day") != day_of(now):  # at most one failed day per calendar day
        state.update(fail_streak=int(num(state.get("fail_streak"))) + 1, fail_day=day_of(now))
    if before and after and after != before:
        state["pending_version"] = after
    write_json(data_dir / STATE, state)
    return state


def main(argv):
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    data_dir = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or claude_dir / "plugins" / "data" / PLUGIN_NAME)
    for flag in ("--claude-dir", "--data-dir"):
        if flag in argv:
            value = Path(argv[argv.index(flag) + 1])
            claude_dir, data_dir = (value, data_dir) if flag == "--claude-dir" else (claude_dir, value)
    try:
        if len(argv) > 1 and argv[1] == "run":
            run_job(claude_dir, data_dir)
        elif len(argv) > 1 and argv[1] == "check":
            root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
            if root:
                for note in check(Path(root), claude_dir, data_dir):
                    print(note)
    except Exception as exc:  # fail silent: a broken update must never break a session
        log(data_dir, f"{argv[1:2]} stopped: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
