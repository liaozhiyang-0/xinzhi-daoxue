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
