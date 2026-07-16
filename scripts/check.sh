#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_bin=".venv/bin/python"

if [[ ! -x "$python_bin" ]]; then
  echo "Virtual environment not found. Run scripts/dev.sh first." >&2
  exit 1
fi

export APP_ENV=test
export DEFAULT_AGENT_PROVIDER=mock
export ALLOW_MOCK_FALLBACK=true
export XINGCHEN_ENABLED=false

"$python_bin" scripts/validate_config.py
"$python_bin" scripts/check_sensitive_files.py
"$python_bin" -m ruff check .
"$python_bin" -m mypy apps/api/app
"$python_bin" -m pytest
"$python_bin" scripts/export_openapi.py

if command -v docker >/dev/null 2>&1; then
  docker compose config --quiet
else
  echo "WARNING: Docker not found; Compose validation skipped." >&2
fi

git diff --check
echo "[xzd] All available checks passed."
