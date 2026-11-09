#!/usr/bin/env python3
"""Config protection: asks before Claude edits an EXISTING linter, formatter or type-check config file.

Standard library only. Idea from ECC's config-protection hook (own code, own list): agents often
loosen the config to make a check pass instead of fixing the code. The decision is two
measurements: the file NAME is in a fixed set (case-insensitive, both / and \\ separators), and the
file already exists. A file that does not exist yet (first creation in a new project) is allowed.
pyproject.toml and tsconfig.json are deliberately not listed: they also carry project metadata or
build settings. Any error means no output (never blocks).
"""
import json
import os

PROTECTED = frozenset(n.lower() for n in [
    # ESLint
    ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml",
    "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts", "eslint.config.mts",
    "eslint.config.cts",
    # Prettier
    ".prettierrc", ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.mjs", ".prettierrc.json",
    ".prettierrc.json5", ".prettierrc.yml", ".prettierrc.yaml", ".prettierrc.toml",
    "prettier.config.js", "prettier.config.cjs", "prettier.config.mjs", "prettier.config.ts",
    # Biome
    "biome.json", "biome.jsonc", ".biome.json", ".biome.jsonc",
    # Python
    "ruff.toml", ".ruff.toml", ".flake8", ".pylintrc", "mypy.ini", ".mypy.ini", "pyrightconfig.json",
    # Shell, CSS, Markdown, Ruby, Go
    ".shellcheckrc",
    ".stylelintrc", ".stylelintrc.json", ".stylelintrc.yml", ".stylelintrc.yaml", ".stylelintrc.js",
    ".stylelintrc.cjs", ".stylelintrc.mjs", "stylelint.config.js", "stylelint.config.cjs",
    "stylelint.config.mjs", "stylelint.config.ts",
    ".markdownlint.json", ".markdownlint.jsonc", ".markdownlint.yaml", ".markdownlint.yml",
    ".markdownlint.cjs", ".markdownlint.mjs", ".markdownlintrc", ".markdownlint-cli2.jsonc",
    ".markdownlint-cli2.yaml", ".markdownlint-cli2.cjs", ".markdownlint-cli2.mjs",
    ".rubocop.yml", ".golangci.yml", ".golangci.yaml",
    # Ignore lists: adding one path silences a check without touching code or config
    ".eslintignore", ".prettierignore", ".stylelintignore", ".markdownlintignore",
])


def target_paths(tool, ti):
    """Every path the tool call would write (MultiEdit entries may carry their own)."""
    out = []
    first = ti.get("notebook_path") if tool == "NotebookEdit" else ti.get("file_path")
    if isinstance(first, str) and first:
        out.append(first)
    edits = ti.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict) and isinstance(e.get("file_path"), str) and e["file_path"]:
                out.append(e["file_path"])
    return out


def main(stdin_text):
    """Hook entry: returns the stdout JSON, or "" for nothing to say. Never raises."""
    try:
        d = json.loads(stdin_text)
        if not isinstance(d, dict) or d.get("tool_name") not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            return ""
        ti = d.get("tool_input")
        if not isinstance(ti, dict):
            return ""
        for p in target_paths(d["tool_name"], ti):
            name = p.replace("\\", "/").rsplit("/", 1)[-1]
            if name.lower() in PROTECTED and os.path.lexists(p):
                reason = (f"CONFIG PROTECTION - {name} is a linter, formatter or type-check config that already "
                          "exists. When a check fails, the fix is usually in the code, not in the config. Only "
                          "change this file if the person asked for a config change; otherwise fix the code.")
                return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                                          "permissionDecisionReason": reason}})
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
        sys.stdout.write(out)
