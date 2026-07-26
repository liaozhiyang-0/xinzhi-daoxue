#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Engine with Compose v2 is required." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker Engine is not running." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example; change development passwords."
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

resolve_knowledge_path() {
  local folder="$1"
  local fallback="$2"
  for candidate in "$repo_root/$folder" "$repo_root/../xinzhi-daoxue/$folder"; do
    if [[ -d "$candidate" ]]; then
      (cd "$candidate" && pwd)
      return
    fi
  done
  echo "$fallback"
}

export KNOWLEDGE_CT_HOST_PATH="${KNOWLEDGE_CT_HOST_PATH:-$(resolve_knowledge_path "电路理论" "$repo_root/local_knowledge/CT")}"
export KNOWLEDGE_AE_HOST_PATH="${KNOWLEDGE_AE_HOST_PATH:-$(resolve_knowledge_path "模电" "$repo_root/local_knowledge/AE")}"
export KNOWLEDGE_DE_HOST_PATH="${KNOWLEDGE_DE_HOST_PATH:-$(resolve_knowledge_path "数电" "$repo_root/local_knowledge/DE")}"
export KNOWLEDGE_SS_HOST_PATH="${KNOWLEDGE_SS_HOST_PATH:-$(resolve_knowledge_path "信号与系统版本一" "$repo_root/local_knowledge/SS")}"
export KNOWLEDGE_DSP_HOST_PATH="${KNOWLEDGE_DSP_HOST_PATH:-$(resolve_knowledge_path "数字信号处理" "$repo_root/local_knowledge/DSP")}"
export KNOWLEDGE_COMM_HOST_PATH="${KNOWLEDGE_COMM_HOST_PATH:-$(resolve_knowledge_path "通信原理" "$repo_root/local_knowledge/COMM")}"

docker compose config --quiet
docker compose up -d --build --wait

health="$(curl --fail --silent http://127.0.0.1:8000/health)"
python3 - "$health" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
required = ("database", "redis", "minio")
if payload.get("status") != "ok" or any(payload.get(key) != "ok" for key in required):
    raise SystemExit(f"degraded health: {payload}")
PY

docker compose ps
echo "[xzd] Ready: http://localhost:8000/docs"
echo "[xzd] MinIO: http://localhost:9001"
