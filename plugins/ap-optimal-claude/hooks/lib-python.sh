# Sourced by the hooks (not a hook itself): sets PYTHON to a Python 3 that really runs,
# or to "" when there is none, so the hook can fail silent.
# Windows (Git Bash sets MSYSTEM): a python.org install gives `python` or `py`, not
# `python3`, and `python3` is often the Microsoft Store placeholder that only prints an
# install hint. So there each candidate is run once instead of trusting `command -v`.
# Elsewhere the first one found is used as is: a probe would double each hook's time.
# PYTHONUTF8=1: Python on Windows otherwise reads and writes text as cp1252.
export PYTHONUTF8=1
PYTHON=""
for _candidate in python3 python py; do
    _path=$(command -v "$_candidate" 2>/dev/null) || continue
    if [ -z "${MSYSTEM:-}" ] || "$_path" -c 'import sys; sys.exit(sys.version_info[0] != 3)' >/dev/null 2>&1; then
        PYTHON=$_path
        break
    fi
done
unset _candidate _path
