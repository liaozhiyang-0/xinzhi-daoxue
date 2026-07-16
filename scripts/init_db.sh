#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$repo_root/.env" ]]; then
  echo ".env not found. Copy .env.example to .env first." >&2
  exit 1
fi
set -a
source "$repo_root/.env"
set +a
export DATABASE_URL="${HOST_DATABASE_URL:-postgresql+asyncpg://xzd_user:xzd_password@localhost:5432/xzd}"
cd "$repo_root/apps/api"
../../.venv/bin/python -m alembic upgrade head
