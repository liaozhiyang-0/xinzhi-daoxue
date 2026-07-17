#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if command -v docker >/dev/null 2>&1; then
  docker compose down
else
  echo "WARNING: Docker not found; no containers were stopped." >&2
fi
