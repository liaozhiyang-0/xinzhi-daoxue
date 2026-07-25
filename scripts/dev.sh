#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python_bin=""
for candidate in python3.12 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1; then
    python_bin="$candidate"
    break
  fi
done
if [[ -z "$python_bin" ]]; then
  echo "Python 3.11 or 3.12 is required." >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for PostgreSQL, Redis, and MinIO." >&2
  exit 1
fi

[[ -d .venv ]] || "$python_bin" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e "apps/api[dev]"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example; change development passwords."
fi

set -a
source .env
set +a
export DATABASE_URL="${HOST_DATABASE_URL:-postgresql+asyncpg://xzd_user:xzd_password@localhost:5432/xzd}"
export REDIS_URL="${HOST_REDIS_URL:-redis://localhost:6379/0}"
export MINIO_ENDPOINT="${HOST_MINIO_ENDPOINT:-localhost:9000}"
resolve_local_knowledge() {
  local folder="$1"
  for candidate in "$repo_root/$folder" "$repo_root/../xinzhi-daoxue/$folder"; do
    if [[ -d "$candidate" ]]; then
      (cd "$candidate" && pwd)
      return
    fi
  done
}

knowledge_path="$(resolve_local_knowledge "电路理论")"
[[ -n "$knowledge_path" ]] && export KNOWLEDGE_CT_PATH="$knowledge_path"
knowledge_path="$(resolve_local_knowledge "模电")"
[[ -n "$knowledge_path" ]] && export KNOWLEDGE_AE_PATH="$knowledge_path"
knowledge_path="$(resolve_local_knowledge "数电")"
[[ -n "$knowledge_path" ]] && export KNOWLEDGE_DE_PATH="$knowledge_path"
knowledge_path="$(resolve_local_knowledge "信号与系统版本一")"
[[ -n "$knowledge_path" ]] && export KNOWLEDGE_SS_PATH="$knowledge_path"
knowledge_path="$(resolve_local_knowledge "数字信号处理")"
[[ -n "$knowledge_path" ]] && export KNOWLEDGE_DSP_PATH="$knowledge_path"
knowledge_path="$(resolve_local_knowledge "通信原理")"
[[ -n "$knowledge_path" ]] && export KNOWLEDGE_COMM_PATH="$knowledge_path"

docker compose up -d postgres redis minio
(cd apps/api && ../../.venv/bin/python -m alembic upgrade head)
exec .venv/bin/python -m uvicorn app.main:app --app-dir apps/api --reload --host 0.0.0.0 --port 8000
