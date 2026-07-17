from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
os.environ["APP_ENV"] = "test"
os.environ["DEFAULT_AGENT_PROVIDER"] = "mock"

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def wait_for_terminal(client: TestClient, task_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        task = client.get(f"/api/v1/tasks/{task_id}").json()
        if task["status"] in {"completed", "failed", "cancelled"}:
            return task
        time.sleep(0.05)
    raise TimeoutError(f"Mock task did not finish: {task_id}")


def main() -> int:
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        settings = Settings(
            app_env="test",
            test_database_url=f"sqlite+aiosqlite:///{temp_path / 'benchmark.db'}",
            redis_url="redis://127.0.0.1:1/0",
            minio_endpoint="127.0.0.1:1",
            local_storage_path=temp_path / "storage",
            sse_heartbeat_seconds=0.05,
        )
        with TestClient(create_app(settings)) as client:
            session = client.post(
                "/api/v1/sessions",
                json={"user_id": "benchmark", "course_id": "CT"},
            ).json()
            for path in sorted((EVAL_ROOT / "cases").glob("*/*.json")):
                case = json.loads(path.read_text(encoding="utf-8"))
                created = client.post(
                    "/api/v1/tasks",
                    json={
                        "session_id": session["id"],
                        "user_id": "benchmark",
                        "course_id": "CT",
                        "canonical_input": {"text": case["question"]},
                        "options": {},
                    },
                )
                created.raise_for_status()
                task = wait_for_terminal(client, created.json()["id"])
                results.append(
                    {
                        "case_id": case["case_id"],
                        "status": task["status"],
                        "provider": task["provider"],
                        "artifact_count": len(task["artifact_ids"]),
                        "latency_ms": (
                            task.get("result_content", {})
                            .get("metrics", {})
                            .get("latency_ms")
                        ),
                        "correctness": "NOT_EVALUATED",
                    }
                )
    output = EVAL_ROOT / "results" / "mock_benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "provider": "mock",
                "warning": "No real circuit-solving correctness was evaluated.",
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Mock benchmark report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
