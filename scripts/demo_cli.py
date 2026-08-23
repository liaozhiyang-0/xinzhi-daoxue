from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "apps/api/app/static/debug"
ROUTES = ("/", "/student", "/debug/rag", "/debug/agents", "/system", "/demo")


def request_json(
    url: str, *, payload: dict[str, object] | None = None
) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=90 if payload else 5) as response:  # noqa: S310
        value: dict[str, object] = json.loads(response.read().decode("utf-8"))
        return value


def preflight(base_url: str) -> int:
    checks: list[tuple[str, bool, str]] = []
    for name in (
        "home.html",
        "rag.html",
        "agents.html",
        "system.html",
        "demo.html",
    ):
        path = STATIC / name
        checks.append((f"静态页面 {name}", path.is_file(), str(path.relative_to(ROOT))))
    demo_image = STATIC / "assets/demo-circuit.svg"
    checks.append(
        ("演示固定图片", demo_image.is_file(), str(demo_image.relative_to(ROOT)))
    )

    online = True
    try:
        health = request_json(f"{base_url}/api/v1/health")
        api_status = str(health.get("status"))
        checks.append(("FastAPI", api_status in {"ok", "degraded"}, api_status))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        online = False
        checks.append(("FastAPI", False, f"无法连接: {exc}"))

    if online:
        _check_routes(base_url, checks)
        _check_rag_status(base_url, checks)
        _check_agent_status(base_url, checks)


    print("芯智导学会议演示 Preflight")
    for name, passed, detail in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    failed = sum(not passed for _, passed, _ in checks)
    print(f"结果: {len(checks) - failed}/{len(checks)} 通过")
    return 1 if failed else 0


def _check_routes(base_url: str, checks: list[tuple[str, bool, str]]) -> None:
    for route in ROUTES:
        try:
            with urlopen(f"{base_url}{route}", timeout=5) as response:  # noqa: S310
                checks.append(
                    (f"页面路由 {route}", response.status == 200, str(response.status))
                )
        except (URLError, TimeoutError, OSError) as exc:
            checks.append((f"页面路由 {route}", False, str(exc)))


def _check_rag_status(base_url: str, checks: list[tuple[str, bool, str]]) -> None:
    try:
        rag = request_json(f"{base_url}/api/v1/debug/rag/status")
        rag_disabled = rag.get("rag_enabled") is False
        vector_count = sum(
            value if isinstance(value := rag.get(field), int) else 0
            for field in ("text_vector_count", "image_vector_count")
        )
        index_ready = bool(rag.get("index_version")) or rag_disabled or vector_count > 0
        checks.extend(
            [
                (
                    "Qdrant",
                    bool(rag.get("vector_store_connected"))
                    or rag.get("rag_enabled") is False,
                    (
                        "disabled by configuration"
                        if rag.get("rag_enabled") is False
                        else str(rag.get("vector_store_connected"))
                    ),
                ),
                (
                    "知识库索引",
                    index_ready,
                    (
                        "disabled by configuration"
                        if rag_disabled
                        else str(rag.get("index_version") or f"vectors:{vector_count}")
                    ),
                ),
                (
                    "LEARN Runtime",
                    bool(rag.get("local_ready")),
                    "configured"
                    if rag.get("local_ready")
                    else "not configured",
                ),
            ]
        )
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        checks.append(("RAG 轻量状态", False, str(exc)))


def _check_agent_status(base_url: str, checks: list[tuple[str, bool, str]]) -> None:
    try:
        agents = request_json(f"{base_url}/api/v1/agents")
        raw_registered = agents.get("agents")
        registered: list[dict[str, object]] = (
            [item for item in raw_registered if isinstance(item, dict)]
            if isinstance(raw_registered, list)
            else []
        )
        solver: dict[str, object] = next(
            (item for item in registered if "SOLVER_CT" in str(item.get("agent_id"))),
            {},
        )
        checks.append(
            (
                "SOLVER_CT Runtime",
                bool(solver.get("configured")),
                "configured" if solver.get("configured") else "not configured",
            )
        )
        checks.append(
            ("演示场景配置", len(registered) > 0, f"{len(registered)} agents")
        )
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        checks.append(("Agent 注册表", False, str(exc)))



def legacy_start(port: int) -> int:
    print("[xzd] demo_cli.py start 已兼容转接到统一启动器。")
    command = [
        sys.executable,
        str(ROOT / "scripts/team_launcher.py"),
        "start",
        "--port",
        str(port),
    ]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="芯智导学会议演示工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("preflight", help="检查会议演示依赖")
    check.add_argument("--base-url", default="http://127.0.0.1:8000")
    start = subparsers.add_parser("start", help="兼容入口；转接统一启动器")
    start.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "start":
        return legacy_start(args.port)
    return preflight(args.base_url.rstrip("/"))


if __name__ == "__main__":
    raise SystemExit(main())
