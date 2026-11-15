#!/usr/bin/env bash
# CometTrain setup. No third-party packages are needed (standard library only),
# so this script only proves the interpreter is new enough and that the tool
# imports cleanly. It installs nothing system-wide, needs no privileges, and
# exits without starting anything.
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "install: $PYTHON was not found on PATH; install Python 3.9 or newer" >&2
  exit 1
fi

"$PYTHON" - <<'PYCHECK'
import sys

if sys.version_info < (3, 9):
    sys.exit(
        "install: Python 3.9 or newer is required, found %s"
        % sys.version.split()[0]
    )
print("install: using Python %s" % sys.version.split()[0])
PYCHECK

"$PYTHON" -m py_compile comettrain.py
"$PYTHON" -c 'import comettrain; print("install: catalogue ready with %d comets" % len(comettrain.catalogue()))'

echo "install: nothing else to do - CometTrain has no third-party dependencies."
echo "install: run it with: python3 comettrain.py list"
echo "install: see every surface with: bash demo.sh"
