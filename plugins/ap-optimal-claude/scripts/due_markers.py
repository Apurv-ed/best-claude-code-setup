#!/usr/bin/env python3
"""Find "Due YYYY-MM-DD" markers (and JSON due items) in a project and format a short due/overdue block.

CLI: due_markers.py <root> [--today YYYY-MM-DD] [--count | --has-markers]
     due_markers.py --intro <data_dir> <project_root>
Stdlib only. Never raises out of the CLI.
"""
import datetime, hashlib, json, pathlib, re, subprocess, sys

MARKER = re.compile(r"\bDue (\d{4}-\d{2}-\d{2}|\d{4}-\d{1,2}-\d{1,2})\b")
BUMP = re.compile(r"\(bumped (\d+)\)")
SKIP_DIRS = ("docs/research/", "docs/decisions/", "docs/transcriptions/", "docs/superpowers/", "docs/SESSION_HANDOFF.md")
SKIP_SEGMENTS = {"node_modules", ".venv", "venv", "dist", "build"}
DONE_STATUS = {"done", "closed", "cancelled", "blocked", "waiting"}
NOT_DONE_STR = {"", "false", "no", "none", "null", "0"}
MAX_BYTES = 2_000_000
MAX_FILES = 2000
HEAD = ("[DUE] Promised items due today or overdue (from Due markers). For each, in this session: do it, or re-date it "
        "with a reason and add or raise (bumped N), or drop it with a reason. Remove the marker when an item is finished.")
INTRO = ('[DUE MARKERS] New: promised follow-ups now carry "Due YYYY-MM-DD" so session start lists them when due. '
         'Tell the user in one plain line that they can say "sort deadlines" to mark this project\'s open deadlines.')


def _read(p):
    with open(p, "rb") as f:
        return f.read(MAX_BYTES).decode("utf-8", errors="ignore")


def _skipped(rel):
    if SKIP_SEGMENTS.intersection(rel.split("/")[:-1]):
        return True
    return rel == "CHANGELOG.md" or rel.endswith("/CHANGELOG.md") or any(rel.startswith(d) or "/" + d in rel for d in SKIP_DIRS)


def _rank(n):
    if n == "STATUS.md":
        return (0, n)
    if n.startswith("docs/") and n.endswith(".md"):
        return (1, n)
    return (2 if n.endswith(".md") else 3, n)


def _files(root):
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "*.md", "*.json"], capture_output=True, encoding="utf-8", errors="replace", timeout=20)
        if out.returncode == 0:
            names = [n.replace("\\", "/") for n in out.stdout.split("\0") if n]
            return sorted((n for n in names if not _skipped(n)), key=_rank)[:MAX_FILES]
    except Exception:
        pass
    names = []
    if (root / "STATUS.md").is_file():
        names.append("STATUS.md")
    d = root / "docs"
    if d.is_dir():
        names += sorted("docs/" + p.name for p in d.glob("*.md"))
    return [n for n in names if not _skipped(n)]


def _parse(s):
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def _md_items(rel, text):
    items, fence = [], False
    for no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence or "~~" in line:
            continue
        m = MARKER.search(line)
        if not m:
            continue
        d = _parse(m.group(1))
        b = BUMP.search(line)
        items.append({"file": rel, "line": no, "date": d, "text": line.strip(), "bumped": int(b.group(1)) if b else 0,
                      "bad": d is None, "key": "%s:%d" % (rel, no), "raw": m.group(0)})
    return items


def _is_done(it):
    if str(it.get("status", "")).strip().lower() in DONE_STATUS:
        return True
    v = it.get("done")
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() not in NOT_DONE_STR
    return bool(v)


def _json_items(rel, text):
    data = json.loads(text)
    rows = data.get("items") if isinstance(data, dict) else data
    out = []
    if not isinstance(rows, list):
        return out
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("due"), str):
            continue
        m = re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", r["due"].strip())
        if not m or _is_done(r):
            continue
        d = _parse(m.group(0))
        title = str(r.get("title") or r.get("text") or "").strip()
        rid = str(r["id"]) if r.get("id") else ""
        out.append({"file": rel, "line": 0, "date": d, "text": ("%s %s" % (rid, title)).strip(), "bumped": 0, "bad": d is None,
                    "key": rid or rel + ":" + r["due"], "raw": "Due " + r["due"], "id": rid})
    return out


def find_items(root):
    root = pathlib.Path(root)
    md, js = [], []
    for rel in _files(root):
        try:
            text = _read(root / rel)
            if rel.endswith(".json"):
                js += _json_items(rel, text)
            else:
                md += _md_items(rel, text)
        except Exception:
            continue
    # same item in a markdown line and a JSON list prints once (markdown wins)
    md_text = "\n".join(i["text"] for i in md)
    js = [i for i in js if not (len(i["id"]) >= 3 and re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(i["id"]), md_text))]
    return md + js


def _loc(it):
    return it["file"] if not it["line"] else "%s:%d" % (it["file"], it["line"])


def _due(items, today):
    return [i for i in items if i["bad"] or i["date"] <= today]


def count_due(root, today):
    return len(_due(find_items(root), today))


def format_due(items, today, max_items=10, per_item=150, limit=1500):
    due = sorted(_due(items, today), key=lambda i: (not i["bad"], i["date"] or datetime.date.min, i["key"]))
    if not due:
        return ""
    lines = []
    for it in due:
        if it["bad"]:
            s = '- BAD DATE %s "%s": fix the date.' % (_loc(it), it["raw"])
        else:
            n = (today - it["date"]).days
            tag = "DUE TODAY (%s)" % it["date"] if n == 0 else "OVERDUE %d day%s (%s)" % (n, "" if n == 1 else "s", it["date"])
            suffix = " - bumped %d times: owner decides" % it["bumped"] if it["bumped"] >= 3 else ""
            s = "- %s %s %s" % (tag, _loc(it), it["text"])
            if len(s) + len(suffix) > per_item:
                s = s[:max(per_item - len(suffix) - 3, 0)] + "..."
            s += suffix
        lines.append(s if len(s) <= per_item else s[:per_item - 3] + "...")
    shown = []
    for s in lines[:max_items]:
        tail = len(due) - len(shown) - 1
        trial = "\n".join([HEAD] + shown + [s] + (["[%d more due: run python3 <path to due_markers.py> . to see all.]" % tail] if tail else []))
        if len(trial) > limit:
            break
        shown.append(s)
    out = [HEAD] + shown
    if len(due) > len(shown):
        out.append("[%d more due: run python3 <path to due_markers.py> . to see all.]" % (len(due) - len(shown)))
    return "\n".join(out)


def _intro(data_dir, root):
    root = pathlib.Path(root).resolve()
    h = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:16]
    flag = pathlib.Path(data_dir) / "due-intro-noted" / h
    if flag.exists() or find_items(root):
        return ""
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("")
    return INTRO


def main(argv):
    try:
        if argv and argv[0] == "--intro":
            out = _intro(argv[1], argv[2])
            if out:
                print(out)
            return 0
        args = [a for a in argv if not a.startswith("--")]
        today = datetime.date.today()
        if "--today" in argv:
            v = argv[argv.index("--today") + 1]
            today = datetime.date.fromisoformat(v)
            args.remove(v)
        root = pathlib.Path(args[0] if args else ".")
        if "--has-markers" in argv:
            return 0 if find_items(root) else 1
        if "--count" in argv:
            print(count_due(root, today))
            return 0
        out = format_due(find_items(root), today)
        if out:
            print(out)
    except Exception:
        if argv and argv[0] == "--intro":
            return 0
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
