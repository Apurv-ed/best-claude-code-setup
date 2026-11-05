#!/usr/bin/env python3
"""Key guard scanner: finds API keys, tokens and passwords in text Claude is about to write.

Standard library only. Rules are the vendored gitleaks rules (key_rules.json, MIT; see
key_rules.LICENSE) and the allowlist logic follows gitleaks' detect code:
  - a rule is skipped unless one of its keywords occurs in the text (case-insensitive);
  - a rule with a `path` fires only when the file path matches it;
  - the secret is capture group `secret_group`, or the first non-empty group, or the whole match;
  - a finding is dropped when its entropy is <= the rule's entropy, or when an allowlist applies
    (condition OR: any non-empty criterion matches; AND: every non-empty criterion matches).

Two extra rules on top of gitleaks, for level "warn" only (the noisy generic rule): placeholder
values and well-known harmless variable names (s3_key, event_key ...) are ignored.

Findings never contain the secret value, only rule id, line number and length.
"""
import json
import math
import os
import re
from bisect import bisect_right
from collections import Counter, namedtuple
from pathlib import Path

Finding = namedtuple("Finding", "rule_id description level line length")

MAX_TEXT = 2_000_000
MAX_FINDINGS = 5
MAX_LINE = 4000  # longer lines (minified code, data URIs) are skipped: Python's regex can backtrack for seconds
ALLOW_MARKERS = ("key-guard: allow", "gitleaks:allow")
# Obvious placeholders: ignored at every level (a Slack webhook with XXXX is not a key).
PLACEHOLDER = re.compile(r"(?i)x{4,}|redacted|<[^>]*>|\$\{[^}]*\}")
# Broader word list, warn level only (the noisy generic rule).
PLACEHOLDER_WORDS = re.compile(r"(?i)your|example|sample|placeholder|dummy|fake|changeme|\.\.\.")
HARMLESS_NAMES = ("s3_key", "event_key", "cache_key", "sort_key", "primary_key", "partition_key",
                  "foreign_key", "idempotency_key")


def load_rules(path=None):
    """Load the rules JSON: explicit path, else env KEY_GUARD_RULES, else key_rules.json beside this file."""
    p = path or os.environ.get("KEY_GUARD_RULES") or str(Path(__file__).resolve().parent / "key_rules.json")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _rx(pattern):
    try:
        return re.compile(pattern)
    except re.error:
        return None


def _compile_allowlist(a):
    return {
        "target": a.get("target") or "secret",
        "and": a.get("condition") == "AND",
        "regexes": [c for c in (_rx(x) for x in a.get("regexes") or []) if c],
        "stopwords": [s.lower() for s in a.get("stopwords") or []],
        "paths": [c for c in (_rx(x) for x in a.get("paths") or []) if c],
    }


def _compiled(rules):
    """Compile every pattern once per loaded dict; cached inside it under '_compiled'."""
    c = rules.get("_compiled")
    if c is not None:
        return c
    out = []
    for r in rules.get("rules", []):
        rx = _rx(r["regex"]) if r.get("regex") else None
        if rx is None:
            continue
        out.append({
            "rule": r, "rx": rx,
            "path": _rx(r["path"]) if r.get("path") else None,
            "keywords": [k.lower() for k in r.get("keywords") or []],
            "allow": [_compile_allowlist(a) for a in r.get("allowlists") or []],
        })
    c = {"rules": out, "top": [_compile_allowlist(a) for a in rules.get("allowlists") or []]}
    rules["_compiled"] = c
    return c


def _entropy(s):
    if not s:
        return 0.0
    n = len(s)
    return -sum(v / n * math.log2(v / n) for v in Counter(s).values())


def _allowed(allowlists, secret, match, line, path):
    for a in allowlists:
        tested = []
        if a["regexes"]:
            subject = {"secret": secret, "match": match, "line": line}[a["target"]] if a["target"] in ("secret", "match", "line") else secret
            tested.append(any(r.search(subject) for r in a["regexes"]))
        if a["stopwords"]:
            low = secret.lower()
            tested.append(any(w in low for w in a["stopwords"]))
        if a["paths"]:
            tested.append(bool(path) and any(r.search(path) for r in a["paths"]))
        if not tested:
            continue
        if (all(tested) if a["and"] else any(tested)):
            return True
    return False


def _secret_of(m, group):
    if group:
        try:
            return m.group(group) or ""
        except IndexError:
            return m.group(0)
    for g in m.groups():
        if g:
            return g
    return m.group(0)


def _warn_noise(secret, match):
    if PLACEHOLDER_WORDS.search(secret):
        return True
    name = re.split(r"[:=]", match, maxsplit=1)[0].strip().strip("\"'`").lower()
    return name.endswith(HARMLESS_NAMES)


def scan(text, rules, path=""):
    """Return up to 5 Findings, block before warn, then by line. Text over 2 MB is skipped."""
    if not text or len(text) > MAX_TEXT:
        return []
    comp = _compiled(rules)
    starts = [0]
    starts.extend(i + 1 for i, ch in enumerate(text) if ch == "\n")
    ends = [s - 1 for s in starts[1:]] + [len(text)]
    scan_text = text
    if any(e - s > MAX_LINE for s, e in zip(starts, ends)):
        # blank over-long lines with spaces: offsets and line numbers stay correct
        parts = [" " * (e - s) if e - s > MAX_LINE else text[s:e] for s, e in zip(starts, ends)]
        scan_text = "\n".join(parts)
    low = scan_text.lower()
    path = path or ""
    found = {}
    for c in comp["rules"]:
        r = c["rule"]
        if c["keywords"] and not any(k in low for k in c["keywords"]):
            continue
        if c["path"] is not None and not (path and c["path"].search(path)):
            continue
        for m in c["rx"].finditer(scan_text):
            secret = _secret_of(m, r.get("secret_group") or 0)
            if not secret:
                continue
            ent = r.get("entropy") or 0
            if ent and _entropy(secret) <= ent:
                continue
            idx = bisect_right(starts, m.start()) - 1
            line = text[starts[idx]:ends[idx]]
            match = m.group(0)
            if any(k in line for k in ALLOW_MARKERS):
                continue
            if _allowed(c["allow"], secret, match, line, path) or _allowed(comp["top"], secret, match, line, path):
                continue
            level = r.get("level", "block")
            if PLACEHOLDER.search(secret):
                continue
            if level == "warn" and _warn_noise(secret, match):
                continue
            lineno = idx + 1
            found.setdefault((r["id"], lineno), Finding(r["id"], r.get("description", ""), level, lineno, len(secret)))
    out = sorted(found.values(), key=lambda f: (f.level != "block", f.line))
    block_lines = {f.line for f in out if f.level == "block"}
    out = [f for f in out if not (f.level == "warn" and f.line in block_lines)]
    return out[:MAX_FINDINGS]


EXEMPT_NAMES = (".env", ".dev.vars")
NOT_EXEMPT = ("example", "sample", "template")


def is_exempt(path):
    """Secret files that are meant to hold keys: .env, .env.<name> (not when the name holds example, sample or template), .dev.vars."""
    name = os.path.basename((path or "").replace("\\", "/")).lower()
    if any(w in name for w in NOT_EXEMPT):
        return False
    return name in EXEMPT_NAMES or name.startswith(".env.")


def added_text(tool_name, tool_input):
    """The text a tool call would add to a file (never the text it removes)."""
    if not isinstance(tool_input, dict):
        return ""
    if tool_name == "Write":
        v = tool_input.get("content")
    elif tool_name == "Edit":
        v = tool_input.get("new_string")
    elif tool_name == "NotebookEdit":
        v = tool_input.get("new_source")
    elif tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return ""
        v = "\n".join(e["new_string"] for e in edits if isinstance(e, dict) and isinstance(e.get("new_string"), str))
    else:
        return ""
    return v if isinstance(v, str) else ""


def main(stdin_text):
    """Hook entry: returns the stdout JSON, or "" for nothing to say. Never raises."""
    try:
        d = json.loads(stdin_text)
        if not isinstance(d, dict):
            return ""
        tool = d.get("tool_name")
        ti = d.get("tool_input")
        if not isinstance(ti, dict):
            return ""
        path = ti.get("notebook_path") if tool == "NotebookEdit" else ti.get("file_path")
        path = path if isinstance(path, str) else ""
        if is_exempt(path):
            return ""
        text = added_text(tool, ti)
        if not text:
            return ""
        findings = scan(text, load_rules(), path)
        name = os.path.basename(path.replace("\\", "/")) or "this file"
        where = f"of {name}" if tool == "Write" else f"of the text being added to {name}"
        block = next((f for f in findings if f.level == "block"), None)
        if block:
            reason = (f"KEY GUARD - line {block.line} {where} matches the {block.rule_id} pattern "
                      f"({block.description}), a value of {block.length} characters. Keys belong in a gitignored "
                      ".env file or the system keychain; the file can hold the variable name instead. If the owner "
                      "confirms it is not a key, the line can carry the comment key-guard: allow.")
            return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                      "permissionDecisionReason": reason}})
        warn = next((f for f in findings if f.level == "warn"), None)
        if warn:
            note = (f"KEY GUARD - line {warn.line} {where} matches the broad key pattern (a value of "
                    f"{warn.length} characters). If it is a real key, it belongs in a gitignored .env file or the "
                    "system keychain, not in this file. If it is not a key, nothing is needed.")
            return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}})
        return ""
    except Exception:
        return ""


if __name__ == "__main__":
    import sys
    try:
        out = main(sys.stdin.read())
    except BaseException:
        out = ""
    if out:
        print(out)
    sys.exit(0)
