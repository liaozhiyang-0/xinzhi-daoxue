#!/usr/bin/env sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  echo "[xzd] Python 3.11-3.13 is required." >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  set -- start
fi
exec "$PYTHON" "$REPO_ROOT/scripts/team_launcher.py" "$@"
