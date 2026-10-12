# Sourced by the hooks (not a hook itself): sets PYTHON to a Python 3 that really runs,
# or to "" when there is none, so the hook can fail silent.
# Also sets ON_WINDOWS=1 under Git Bash (MSYSTEM from Git's launcher, OSTYPE from bash).
# Windows: depending on how Python was installed there may be only `python` or `py`, and
# `python3` can be the Microsoft Store placeholder that only prints an install hint. So
# there each candidate is run once instead of trusting `command -v`.
# Elsewhere the first one found is used as is (a probe would double each hook's time),
# except Apple's /usr/bin/python3 stub on a Mac without the Command Line Tools.
# PYTHONUTF8=1: Python on Windows otherwise reads and writes text as cp1252.
export PYTHONUTF8=1
ON_WINDOWS=""
case "${OSTYPE:-}" in msys* | cygwin*) ON_WINDOWS=1 ;; esac
[ -n "${MSYSTEM:-}" ] && ON_WINDOWS=1
PYTHON=""
for _candidate in python3 python py; do
    _path=$(command -v "$_candidate" 2>/dev/null) || continue
    if [ -n "$ON_WINDOWS" ]; then
        "$_path" -c 'import sys; sys.exit(sys.version_info[0] != 3)' >/dev/null 2>&1 || continue
    elif [ "$_path" = /usr/bin/python3 ] && ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
        [ -x /usr/bin/xcode-select ] && continue
    fi
    PYTHON=$_path
    break
done
unset _candidate _path
