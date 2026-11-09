#!/usr/bin/env python3
"""Safety guard for Claude Code (PreToolUse hook, run through hooks/safety-guard.sh).

Keeps the shared setup from damaging a non-technical person's laptop (ADR-0105):
  A. Folder guard: when the project folder is the home folder, Downloads, Desktop or
     Documents (or the OneDrive twins), Claude does not change files there.
  B/C. Shell parser: finds what a Bash command writes or deletes (after unwrapping sudo,
     env, xargs, bash -c ...) and decides: recursive delete anywhere = deny (temp folders
     excepted), delete outside the allowed places = deny, write outside = OUTSIDE_WRITE_DECISION.
Standard library only. Silent unless it decides something. Any problem means no output.

Other uses:  safety_guard.py --candidates          list existing project-folder candidates
             safety_guard.py --set-folder PATH     remember where projects are kept
"""
import json
import os
import re
import shlex
import sys
from collections import namedtuple

OUTSIDE_WRITE_DECISION = "ask"
CANDIDATES = ["~/Claude Projects", "~/Projects", "~/projects", "~/Code", "~/code", "~/dev",
              "~/Documents/dev", "~/Documents/Projects"]
DEFAULT_FOLDER = "~/Claude Projects"
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
NO_FILE = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/fd/1", "/dev/fd/2")
SUB_HEREDOC = re.compile(r"""\$\([^\n]*?<<-?[ \t]*['"]?([\w.-]+)['"]?[^\n]*\n""")
SEMI = "\x01;"  # an escaped semicolon (find -exec ... \;), kept apart from the shell's own ;
SEPARATORS = set("();&|")
REDIRECTS = {">", ">>", ">|", "&>", "&>>", ">&", "<", "<<", "<<<", "<&", "<>"}
OUT_REDIRECTS = {">", ">>", ">|", "&>", "&>>", ">&", "<>"}
ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SPECIAL = "$`*?[{"
SHELLS = ("bash", "sh", "zsh", "dash", "ksh")
MAX_DEPTH = 5
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "{", "}", "!"}

Op = namedtuple("Op", "name kind recursive targets unknown")  # kind: write | delete


# ----------------------------------------------------------------------------- paths

def home_dir():
    return os.path.expanduser("~")


def claude_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(home_dir(), ".claude")


def norm(p):
    return os.path.normcase(os.path.realpath(p))


def inside(path, base):
    return path == base or path.startswith(base.rstrip(os.sep) + os.sep)


def expand_user(p):
    if p == "~" or p.startswith("~/") or p.startswith("~\\"):
        return home_dir() + p[1:]
    return p


def guarded_folders():
    """Exactly these folders (not what is below them)."""
    home = home_dir()
    out = [home] + [os.path.join(home, n) for n in ("Downloads", "Desktop", "Documents")]
    try:
        for name in sorted(os.listdir(home)):
            if name.startswith("OneDrive"):
                out += [os.path.join(home, name, "Desktop"), os.path.join(home, name, "Documents")]
    except OSError:
        pass
    return [norm(p) for p in out]


def temp_places():
    """Where scratch work is fine. SAFETY_GUARD_TEMP (os.pathsep list) replaces the list; for tests."""
    override = os.environ.get("SAFETY_GUARD_TEMP")
    if override is not None:
        return [norm(p) for p in override.split(os.pathsep) if p]
    out = ["/tmp", "/private/tmp", "/var/folders"]
    for var in ("TMPDIR", "TEMP", "TMP"):
        if os.environ.get(var):
            out.append(os.environ[var])
    return [norm(p) for p in out]


def read_lines(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read().splitlines()
    except OSError:
        return []


def allow_file_entries():
    out = []
    for line in read_lines(os.path.join(claude_dir(), "safety-allow.txt")):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(norm(expand_user(line)))
    return out


def additional_directories(root):
    out = []
    for path in (os.path.join(claude_dir(), "settings.json"), os.path.join(root, ".claude", "settings.json"),
                 os.path.join(root, ".claude", "settings.local.json")):
        try:
            with open(path, encoding="utf-8-sig") as f:
                dirs = json.load(f).get("permissions", {}).get("additionalDirectories", [])
        except (OSError, ValueError, AttributeError):
            continue
        for d in dirs if isinstance(dirs, list) else []:
            if isinstance(d, str) and d:
                d = expand_user(d)
                out.append(norm(d if os.path.isabs(d) else os.path.join(root, d)))
    return out


def allowed_places(root):
    return [root] + additional_directories(root) + temp_places() + [norm(claude_dir())] + allow_file_entries()


def projects_folder():
    lines = read_lines(os.path.join(claude_dir(), "projects-folder.txt"))
    return lines[0].strip() if lines and lines[0].strip() else os.path.normpath(expand_user(DEFAULT_FOLDER))


def is_guarded(root):
    return root in guarded_folders() and root not in allow_file_entries()


# ----------------------------------------------------------------------------- parsing

def strip_noise(cmd):
    """Quote-aware: drop comments (a # at the start of a word, to the end of the line) and
    heredoc bodies (the <<EOF line stays, so its redirect still counts, and so does what follows
    the terminator)."""
    out, quote, i, n, pending = [], None, 0, len(cmd), []
    while i < n:
        c = cmd[i]
        sub = SUB_HEREDOC.match(cmd, i) if c == "$" and quote != "'" and not cmd.startswith("$((", i) else None
        if c == "$" and quote != "'" and cmd.startswith("$((", i) and cmd.find("))", i) > 0:
            end = cmd.find("))", i) + 2  # arithmetic: its << is a shift, not a heredoc
            out.append(cmd[i:end])
            i = end
            continue
        if sub:  # a heredoc inside $( ), the usual commit message form: its text is not commands
            out.append(sub.group(0))
            j = sub.end()
            while j < n:
                eol = cmd.find("\n", j)
                eol = n if eol < 0 else eol
                line = cmd[j:eol]
                j = eol + 1
                if line.strip() == sub.group(1):
                    break
            i = j
            continue
        if quote == "'":
            out.append(c)
            quote = None if c == "'" else quote
        elif quote == '"':
            if c == "\\" and i + 1 < n:
                out.append(c + cmd[i + 1])
                i += 1
            else:
                out.append(c)
                quote = None if c == '"' else quote
        elif c in "'\"":
            quote = c
            out.append(c)
        elif c == "\\" and i + 1 < n:
            out.append(c + cmd[i + 1])
            i += 1
        elif c == "#" and (i == 0 or cmd[i - 1] in " \t\n;&|("):
            while i + 1 < n and cmd[i + 1] != "\n":
                i += 1
        elif c == "<" and cmd.startswith("<<", i) and not cmd.startswith("<<<", i):
            j = i + 2
            dash = j < n and cmd[j] == "-"
            j += 1 if dash else 0
            while j < n and cmd[j] in " \t":
                j += 1
            k, word = j, []
            while k < n and cmd[k] not in " \t\n;&|<>()":
                if cmd[k] in "'\"":
                    q = cmd[k]
                    k += 1
                    while k < n and cmd[k] != q:
                        word.append(cmd[k])
                        k += 1
                    k += 1
                else:
                    word.append(cmd[k])
                    k += 1
            if word:
                pending.append("".join(word))
            out.append(cmd[i:k])
            i = k - 1
        elif c == "\n" and pending:
            out.append("\n")
            j = i + 1
            for delim in pending:
                while j < n:
                    eol = cmd.find("\n", j)
                    eol = n if eol < 0 else eol
                    line = cmd[j:eol]
                    j = eol + 1
                    if line.strip() == delim:
                        break
            pending = []
            i = j - 1
        else:
            out.append(c)
        i += 1
    return "".join(out)


def substitutions(text):
    """Inner text of every $( ... ) and `...` (also inside double quotes; not inside single quotes)."""
    found, quote, i, n = [], None, 0, len(text)
    while i < n:
        c = text[i]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\" and i + 1 < n:
            i += 1
        elif c == "'" and quote is None:
            quote = "'"
        elif c == '"':
            quote = None if quote == '"' else '"'
        elif c == "$" and text.startswith("$(", i) and not text.startswith("$((", i):
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            found.append(text[i + 2:j - 1] if depth == 0 else text[i + 2:])
        elif c == "`":
            j = text.find("`", i + 1)
            found.append(text[i + 1:j if j >= 0 else n])
            i = j if j >= 0 else n
        i += 1
    return found


def prepare(cmd):
    """Quote-aware pre-pass: newlines become ';', escaped ; ( ) & | become marked words,
    a file-descriptor digit in front of a redirect (2>&1) is dropped."""
    out, quote, i, n = [], None, 0, len(cmd)
    while i < n:
        c = cmd[i]
        if quote == "'":
            out.append(c)
            quote = None if c == "'" else quote
        elif quote == '"':
            if c == "\\" and i + 1 < n:
                out.append(c + cmd[i + 1])
                i += 1
            else:
                out.append(c)
                quote = None if c == '"' else quote
        elif c in "'\"":
            quote = c
            out.append(c)
        elif c == "\\" and i + 1 < n:
            nxt = cmd[i + 1]
            out.append("\x01" + nxt if nxt in "();&|<>" else c + nxt)
            i += 1
        elif c == "\n":
            out.append(" ; ")
        elif c.isdigit() and i + 1 < n and cmd[i + 1] in "<>" and (i == 0 or cmd[i - 1] in " \t\n;&|("):
            pass
        else:
            out.append(c)
        i += 1
    return "".join(out)


def tokenize(cmd):
    lex = shlex.shlex(prepare(cmd), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""  # strip_noise already removed real comments; # inside a word is text
    return list(lex)


def is_separator(tok):
    return bool(tok) and tok not in REDIRECTS and set(tok) <= SEPARATORS


def split_simple(tokens):
    cur = []
    for tok in tokens:
        if is_separator(tok):
            if cur:
                yield cur
            cur = []
        else:
            cur.append(tok)
    if cur:
        yield cur


def clean(w):
    return w if w == SEMI else w.replace("\x01", "")


def cmdname(word):
    name = re.split(r"[\\/]", word)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def resolve(word, cwd):
    """Absolute normalised path for a command-line word, or None when it cannot be known."""
    if not word or word == "-":
        return None
    w = word.replace("${HOME}", home_dir()).replace("$HOME", home_dir())
    if w.startswith("~") and not (w == "~" or w.startswith("~/") or w.startswith("~\\")):
        return None
    w = expand_user(w)
    if os.name == "nt" and re.match(r"^/[a-zA-Z](/|$)", w):
        w = w[1].upper() + ":/" + w[3:]  # Git Bash writes C:\\x as /c/x
    cut = min((w.find(ch) for ch in SPECIAL if ch in w), default=-1)
    if cut >= 0:
        if "/" not in w[:cut]:
            # A bare glob or $(...) acts on the current folder; a plain $VAR could be anywhere.
            plain_var = w[cut] == "$" and w[cut:] != "$" and not w[cut:].startswith("$(")  # a lone $ is a split $(
            return None if plain_var or not cwd else norm(cwd)
        w = w[:w.rindex("/", 0, cut)] or "/"
    if not os.path.isabs(w):
        if not cwd:
            return None
        w = os.path.join(cwd, w)
    return norm(w)


def positional(args, takes_arg=()):
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            out += args[i + 1:]
            break
        if a in takes_arg:
            i += 2
            continue
        if a.startswith("-") and a != "-":
            i += 1
            continue
        out.append(a)
        i += 1
    return out


def option_value(args, short=(), long=()):
    """Values given to the options in `short` (-o X) or `long` (--output X / --output=X)."""
    vals = []
    for i, a in enumerate(args):
        if a in short or a in long:
            if i + 1 < len(args):
                vals.append(args[i + 1])
        else:
            for lg in long:
                if a.startswith(lg + "="):
                    vals.append(a[len(lg) + 1:])
    return vals


def has_flag(args, letters, long=()):
    for a in args:
        if a == "--":
            break
        if a in long:
            return True
        if a.startswith("-") and not a.startswith("--") and len(a) > 1 and any(c in letters for c in a[1:]):
            return True
    return False


class Ctx:
    def __init__(self, cwd):
        self.cwd = cwd


def add(ops, ctx, name, kind, words, recursive=False, unknown=False):
    words = [w for w in words if w not in NO_FILE]
    ops.append(Op(name, kind, recursive, [resolve(w, ctx.cwd) for w in words], unknown))


def analyze(cmd, ctx, depth=0):
    ops = []
    if depth > MAX_DEPTH:
        return ops
    cmd = strip_noise(cmd)
    for inner in substitutions(cmd):
        ops.extend(analyze(inner, Ctx(ctx.cwd), depth + 1))
    try:
        tokens = tokenize(cmd)
    except ValueError:
        return ops
    for words in split_simple(tokens):
        simple(words, ctx, ops, depth)
    return ops


def strip_redirects(words, ctx, ops):
    kept, i = [], 0
    while i < len(words):
        w = words[i]
        if w in REDIRECTS:
            nxt = words[i + 1] if i + 1 < len(words) else None
            if nxt is not None and w in OUT_REDIRECTS and not (w == ">&" and (nxt.isdigit() or nxt == "-")):
                target = clean(nxt)
                if target not in NO_FILE:
                    add(ops, ctx, "redirect", "write", [target])
            i += 2
        else:
            kept.append(w)
            i += 1
    return kept


def skip_options(args, takes_arg=()):
    i = 0
    while i < len(args) and args[i].startswith("-") and args[i] != "-":
        if args[i] == "--":
            i += 1
            break
        i += 2 if args[i] in takes_arg else 1
    return args[i:]


def simple(words, ctx, ops, depth, unknown=False):
    if depth > MAX_DEPTH:
        return
    words = strip_redirects(words, ctx, ops)
    words = [clean(w) if w != SEMI else w for w in words]
    while words and (ENV_RE.match(words[0]) or words[0] in KEYWORDS):
        words = words[1:]
    if not words:
        return
    name, args = cmdname(words[0]), words[1:]
    if name == "cd":
        rest = positional(args)
        ctx.cwd = resolve(rest[0], ctx.cwd) if rest else norm(home_dir())
        return
    if name in ("sudo", "doas"):
        return simple(skip_options(args, {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U", "--user", "--group"}),
                      ctx, ops, depth + 1, unknown)
    if name == "env":
        rest = skip_options(args, {"-u", "-C", "-S"})
        return simple(rest, ctx, ops, depth + 1, unknown)
    if name == "command":
        if args and args[0] in ("-v", "-V"):
            return
        return simple(skip_options(args), ctx, ops, depth + 1, unknown)
    if name in ("nohup", "time", "exec", "builtin", "nice"):
        return simple(skip_options(args, {"-n"}), ctx, ops, depth + 1, unknown)
    if name == "timeout":
        rest = skip_options(args, {"-s", "-k", "--signal", "--kill-after"})
        return simple(rest[1:], ctx, ops, depth + 1, unknown)
    if name == "eval":
        ops.extend(analyze(" ".join(args), ctx, depth + 1))
        return
    if name == "xargs":
        rest = skip_options(args, {"-n", "-I", "-L", "-P", "-d", "-E", "-s", "-a", "-J", "-R", "-S", "-l"})
        return simple(rest, ctx, ops, depth + 1, True)
    if name in SHELLS:
        for i, a in enumerate(args):
            if a.startswith("-") and not a.startswith("--") and "c" in a[1:] and i + 1 < len(args):
                saved = ctx.cwd
                ops.extend(analyze(args[i + 1], ctx, depth + 1))
                ctx.cwd = saved if ctx.cwd is None else ctx.cwd
                return
        return
    handler = HANDLERS.get(name)
    if handler:
        handler(name, args, ctx, ops, unknown)


def h_delete(name, args, ctx, ops, unknown):
    rec = name == "shred" or has_flag(args, "rR", ("--recursive",)) or any(
        a.startswith("--rec") and "--recursive".startswith(a.split("=")[0]) for a in args if a != "--")
    add(ops, ctx, name, "delete", positional(args), rec, unknown)


def h_write_all(name, args, ctx, ops, unknown):
    skip = {"touch": {"-t", "-d", "-r", "--date", "--reference"}, "mkdir": {"-m", "--mode"}}.get(name, ())
    add(ops, ctx, name, "write", positional(args, skip), False, unknown)


def h_last_arg(name, args, ctx, ops, unknown):
    pos = positional(args, {"-t", "--target-directory", "-S", "--suffix", "-e", "--rsh"})
    dest = option_value(args, ("-t",), ("--target-directory",))
    if dest:
        sources = pos
    else:
        dest, sources = pos[-1:], pos[:-1]
    add(ops, ctx, name, "write", dest, False, unknown)
    if name == "mv":
        add(ops, ctx, name, "delete", sources, False, unknown)


def h_chmod(name, args, ctx, ops, unknown):
    pos, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos += args[i + 1:]
            break
        if re.fullmatch(r"-[RfvhHLPc]+", a) or (a.startswith("--") and a != "--"):
            i += 1
            continue
        pos.append(a)
        i += 1
    add(ops, ctx, name, "write", pos[1:], False, unknown)


def h_sed(name, args, ctx, ops, unknown):
    """Targets of sed -i: the files, not the empty BSD suffix, the first expression or -e/-f values."""
    in_place, scripted, files, i = False, False, [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            files += args[i + 1:]
            break
        if a in ("--expression", "--file") or (a.startswith("-") and not a.startswith("--") and len(a) > 1 and a[-1] in "ef"
                                               and "i" not in a):
            scripted = True
            i += 2
            continue
        if a.startswith("--expression=") or a.startswith("--file="):
            scripted = True
        elif a == "--in-place" or a.startswith("--in-place="):
            in_place = True
        elif a.startswith("-") and not a.startswith("--") and len(a) > 1:
            if "i" in a:
                in_place = True
                if a.endswith("i") and i + 1 < len(args) and args[i + 1] == "":
                    i += 1  # the empty backup suffix (macOS)
        elif not a.startswith("-"):
            files.append(a)
        i += 1
    if in_place:
        add(ops, ctx, name, "write", files if scripted else files[1:], False, unknown)


def h_curl(name, args, ctx, ops, unknown):
    add(ops, ctx, name, "write", option_value(args, ("-o",), ("--output",)), False, unknown)


def h_wget(name, args, ctx, ops, unknown):
    add(ops, ctx, name, "write", option_value(args, ("-O",), ("--output-document",)), False, unknown)


def h_dd(name, args, ctx, ops, unknown):
    add(ops, ctx, name, "write", [a[3:] for a in args if a.startswith("of=")], False, unknown)


def h_unzip(name, args, ctx, ops, unknown):
    add(ops, ctx, name, "write", option_value(args, ("-d",)), False, unknown)


def h_tar(name, args, ctx, ops, unknown):
    extracting = any(a in ("--extract", "--get") for a in args)
    for k, a in enumerate(args):
        if a.startswith("-") and not a.startswith("--") and "x" in a:
            extracting = True
        elif k == 0 and not a.startswith("-") and "x" in a:
            extracting = True  # old style: tar xzf a.tgz
    if not extracting:
        return
    targets = option_value(args, ("-C",), ("--directory",))
    for i, a in enumerate(args):
        if re.fullmatch(r"-[A-Za-z]+C", a) and i + 1 < len(args):
            targets.append(args[i + 1])
        elif a.startswith("-C") and len(a) > 2:
            targets.append(a[2:])
    add(ops, ctx, name, "write", targets, False, unknown)


def h_find(name, args, ctx, ops, unknown):
    starts = []
    for a in args:
        if a.startswith("-") or a in ("!", "(", ")"):
            break
        starts.append(a)
    starts = starts or ["."]
    if "-delete" in args:
        add(ops, ctx, name, "delete", starts, True, unknown)
    for i, a in enumerate(args):
        if a in ("-exec", "-execdir", "-ok", "-okdir"):
            sub = []
            for w in args[i + 1:]:
                if w in (SEMI, ";", "+"):
                    break
                sub.append(w)
            if sub and cmdname(sub[0]) == "rm":
                add(ops, ctx, name, "delete", starts, True, unknown)
            elif sub:  # {} stands for each start path; depth at the limit, so only direct handlers run
                for start in starts:
                    simple([start if w == "{}" else w for w in sub], ctx, ops, MAX_DEPTH - 1, True)


def h_git(name, args, ctx, ops, unknown):
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            break
    if i < len(args) and args[i] == "clean" and has_flag(args[i + 1:], "f", ("--force",)):
        add(ops, ctx, "git clean", "delete", [ctx.cwd] if ctx.cwd else [], True, unknown)


HANDLERS = {
    "rm": h_delete, "rmdir": h_delete, "unlink": h_delete, "shred": h_delete,
    "tee": h_write_all, "touch": h_write_all, "mkdir": h_write_all,
    "mv": h_last_arg, "cp": h_last_arg, "rsync": h_last_arg, "install": h_last_arg, "ln": h_last_arg,
    "chmod": h_chmod, "chown": h_chmod, "chgrp": h_chmod,
    "sed": h_sed, "curl": h_curl, "wget": h_wget, "dd": h_dd, "unzip": h_unzip, "tar": h_tar,
    "find": h_find, "git": h_git,
}


# ----------------------------------------------------------------------------- decisions

def in_any(path, bases):
    return path is not None and any(inside(path, b) for b in bases)


def changes_files(ops, offered=()):
    """For the folder guard: any write or delete target (temp places, the offered projects folder and
    /dev/null do not count)."""
    temp = temp_places() + list(offered)
    for op in ops:
        if op.unknown and not [t for t in op.targets if t]:
            return True
        if any(t is not None and not in_any(t, temp) for t in op.targets):
            return True
    return False


def protected_files():
    cd = norm(claude_dir())
    return [os.path.join(cd, n) for n in ("safety-allow.txt", "settings.json", "settings.local.json")]


def offered_folders():
    """Where the folder guard's reason sends the person: the chosen projects folder, or (none chosen yet)
    every existing candidate plus the default."""
    chosen = os.path.join(claude_dir(), "projects-folder.txt")
    if read_lines(chosen) and read_lines(chosen)[0].strip():
        return [norm(projects_folder())]
    return [norm(expand_user(c)) for c in existing_candidates() + [DEFAULT_FOLDER]]


def decide_bash(ops, root, extra=()):
    allowed, temp = allowed_places(root) + list(extra), temp_places()
    protect = protected_files()
    for op in ops:
        if op.kind in ("write", "delete") and any(t in protect for t in op.targets if t):
            return "deny", ("SAFETY GUARD - stopped '" + op.name + "': this file holds the safety settings and only the person "
                            "can change it. Tell the person what you wanted changed and ask them to edit it themselves.")
    for op in ops:
        if op.kind == "delete" and op.recursive:
            if op.unknown or not op.targets or not all(in_any(t, temp) for t in op.targets):
                return "deny", (f"SAFETY GUARD - stopped '{op.name}': a recursive delete can wipe many files at once and "
                                "cannot be undone. Tell the person what you wanted to remove and ask them to do it themselves "
                                "if they really want it (deleting inside a temp folder is allowed).")
    for op in ops:
        if op.kind == "delete":
            bad = [t for t in op.targets if t is not None and not in_any(t, allowed)]
            if bad:
                return "deny", (f"SAFETY GUARD - stopped '{op.name}': it would delete or move away {os.path.basename(bad[0]) or bad[0]} "
                                "outside this project. Ask the person to do that themselves, or to list the folder in "
                                "~/.claude/safety-allow.txt if Claude may change it.")
    for op in ops:
        if op.kind == "write":
            bad = [t for t in op.targets if t is not None and not in_any(t, allowed)]
            if bad:
                return OUTSIDE_WRITE_DECISION, (f"SAFETY GUARD - '{op.name}' would write to {bad[0]}, outside this project. "
                                                "Check with the person before going on.")
    return None, ""


def folder_reason(root):
    return (f"SAFETY GUARD - this folder ({os.path.basename(root) or root}) holds personal files, so Claude does not change "
            f"anything here. Offer to make a project folder inside {projects_folder()} and tell the person to restart "
            "Claude in that new folder.")


def verdict(decision, reason):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                              "permissionDecisionReason": reason}})


def main(stdin_text):
    """Hook entry: returns the stdout JSON, or "" for nothing to say. Never raises."""
    try:
        d = json.loads(stdin_text)
        if not isinstance(d, dict):
            return ""
        tool, ti, cwd = d.get("tool_name"), d.get("tool_input"), d.get("cwd")
        if not isinstance(ti, dict):
            return ""
        root = os.environ.get("CLAUDE_PROJECT_DIR") or (cwd if isinstance(cwd, str) else "")
        if not root:
            return ""
        root = norm(root)
        guarded = is_guarded(root)
        if tool in WRITE_TOOLS:
            return verdict("deny", folder_reason(root)) if guarded else ""
        if tool != "Bash" or not isinstance(ti.get("command"), str):
            return ""
        ops = analyze(ti["command"], Ctx(norm(cwd) if isinstance(cwd, str) and cwd else root))
        offered = offered_folders() if guarded else []
        if guarded and changes_files(ops, offered):
            return verdict("deny", folder_reason(root))
        decision, reason = decide_bash(ops, root, offered)
        return verdict(decision, reason) if decision else ""
    except Exception:
        return ""


# ----------------------------------------------------------------------------- projects folder

def existing_candidates():
    out = []
    for c in CANDIDATES:
        p = expand_user(c)
        if os.path.isdir(p) and not any(os.path.samefile(p, q) for q in out):
            out.append(p)
    return out[:5]


def set_folder(path):
    """Create and remember the projects folder. Returns (ok, message)."""
    if not path or not path.strip():
        return False, "No folder given."
    if "<" in path or ">" in path:
        return False, "That folder name has characters (< or >) that cannot be used."
    if "$" in path or "`" in path:
        return False, "Give the folder's full path, without $ or backticks."
    p = expand_user(path.strip())
    if not os.path.isabs(p):
        return False, "Give the folder's full path, starting with ~/ or /."
    p = os.path.abspath(p)
    home = norm(home_dir())
    low = os.path.normcase(norm(p)).lower()
    if low in [g.lower() for g in guarded_folders()]:
        return False, f"{p} is a folder that holds personal files; pick a folder inside it or elsewhere."
    if not inside(norm(p), home):
        return False, f"{p} is not inside your home folder."
    for bad in [os.path.join(home, ".ssh"), os.path.join(home, "Library"), norm(claude_dir())]:
        if inside(low, os.path.normcase(bad).lower()):
            return False, f"{p} is a system or settings folder; pick another."
    rel = os.path.relpath(norm(p), home)
    if rel.split(os.sep)[0].startswith("."):
        return False, f"{p} is a hidden folder; pick one that is not."
    os.makedirs(p, exist_ok=True)
    os.makedirs(claude_dir(), exist_ok=True)
    with open(os.path.join(claude_dir(), "projects-folder.txt"), "w", encoding="utf-8") as f:
        f.write(p + "\n")
    return True, f"Projects folder set to {p}"


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--candidates":
        print("\n".join(existing_candidates()))
        sys.exit(0)
    if args and args[0] == "--set-folder":
        if len(args) < 2:
            print("usage: safety_guard.py --set-folder PATH")
            sys.exit(1)
        try:
            ok, msg = set_folder(args[1])
        except OSError as exc:
            ok, msg = False, f"Could not use that folder ({exc.__class__.__name__})."
        print(msg)
        sys.exit(0 if ok else 1)
    try:
        out = main(sys.stdin.read())
    except BaseException:
        out = ""
    if out:
        print(out)
    sys.exit(0)
