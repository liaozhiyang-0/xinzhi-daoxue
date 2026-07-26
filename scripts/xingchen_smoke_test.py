from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from time import perf_counter

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402


async def run() -> int:
    if not (ROOT / ".env").is_file():
        print("ERROR: 当前 worktree 缺少 .env，请在本机创建后再运行。")
        return 2
    settings = Settings()
    if not settings.xingchen_runtime_available:
        print("ERROR: XINGCHEN_ENABLED、Key、Secret 或 Flow ID 配置不完整。")
        return 2
    payload = {
        "flow_id": settings.xingchen_solver_ct_flow_id,
        "uid": settings.xingchen_uid,
        "parameters": {"AGENT_USER_INPUT": "你好"},
        "ext": {"caller": "workflow"},
        "stream": False,
    }
    if settings.xingchen_bot_id.strip():
        payload["ext"]["bot_id"] = settings.xingchen_bot_id.strip()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": (
            "Bearer "
            f"{settings.xingchen_api_key.get_secret_value()}:"
            f"{settings.xingchen_api_secret.get_secret_value()}"
        ),
    }
    url = settings.xingchen_base_url.rstrip("/") + settings.xingchen_workflow_path
    started = perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=settings.xingchen_timeout_seconds
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        print(f"ERROR: {type(exc).__name__}")
        return 1
    print(f"HTTP status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
    print(f"Elapsed: {int((perf_counter() - started) * 1000)} ms")
    print("Response body:")
    print(response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
