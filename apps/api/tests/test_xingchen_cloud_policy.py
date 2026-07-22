from __future__ import annotations

from typing import Any

from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AgentResult, RunMetrics
from app.core.config import Settings
from app.main import create_app
from app.providers.base import AgentProvider
from fastapi.testclient import TestClient
from pydantic import SecretStr


class CountingXingchenProvider(AgentProvider):
    provider_name = "xingchen"

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = True,
    ) -> AgentResult:
        del stream
        self.calls.append(agent_id)
        business_data: dict[str, Any] = {
            "learning_objectives": ["解释电容连续性"],
            "lesson_flow": ["概念导入", "例题讨论"],
            "activities": ["小组讨论"],
            "formative_assessment": ["出口题"],
        }
        return AgentResult(
            agent_id=agent_id,
            provider=self.provider_name,
            answer="## 星辰教案结果\n\n已生成经授权的教案。",
            structured_result={
                "status": "completed",
                "business_data": business_data,
            },
            business_data=business_data,
            cloud_status="cloud_success",
            request_id=str(request.options.get("request_id", "")),
            task_id=request.task_id,
            metrics=RunMetrics(model_calls=1),
        )

    async def cancel(self, run_id: str) -> None:
        del run_id

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed", "provider": self.provider_name}


def _xingchen_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "xingchen_enabled": True,
            "xingchen_api_key": SecretStr("test-key"),
            "xingchen_api_secret": SecretStr("test-secret"),
            "xingchen_lesson_prep_flow_id": "lesson-flow",
            "xingchen_fallback_router_flow_id": "router-flow",
            "xingchen_workflows_default_enabled": False,
            "iflytek_spark_enabled": False,
            "dashscope_enabled": False,
        }
    )


def _lesson_payload(
    session_id: str, *, allow_cloud: bool | None = None
) -> dict[str, Any]:
    options: dict[str, Any] = {"request_id": f"lesson-{allow_cloud}"}
    if allow_cloud is not None:
        options["allow_cloud"] = allow_cloud
    return {
        "session_id": session_id,
        "user_id": "teacher-cloud-policy",
        "user_role": "teacher",
        "scene": "teaching",
        "course_id": "CT",
        "intent": "lesson_prep",
        "canonical_input": {"text": "请设计电容连续性课堂教案"},
        "attachments": [],
        "context_refs": [],
        "options": options,
    }


def test_task_runner_does_not_call_xingchen_without_explicit_authorization(
    settings: Settings,
) -> None:
    app = create_app(_xingchen_settings(settings))
    provider = CountingXingchenProvider()
    with TestClient(app) as client:
        app.state.provider = provider
        app.state.task_runner.provider = provider
        session = client.post(
            "/api/v1/sessions",
            json={
                "user_id": "teacher-cloud-policy",
                "course_id": "CT",
                "title": "星辰降级策略",
            },
        ).json()
        created = client.post(
            "/api/v1/tasks", json=_lesson_payload(session["id"])
        )
        assert created.status_code == 202

        task_id = created.json()["id"]
        for _ in range(250):
            task = client.get(f"/api/v1/tasks/{task_id}").json()
            if task["status"] in {"completed", "failed", "cancelled"}:
                break
        else:
            raise AssertionError("task did not finish")

    assert task["status"] == "completed"
    assert provider.calls == []
    assert task["result_content"]["fallback_reason"] == "cloud_opt_out"
    assert task["result_content"]["cloud_status"] == "not_requested"


def test_task_runner_calls_xingchen_only_after_explicit_authorization(
    settings: Settings,
) -> None:
    app = create_app(_xingchen_settings(settings))
    provider = CountingXingchenProvider()
    with TestClient(app) as client:
        app.state.provider = provider
        app.state.task_runner.provider = provider
        session = client.post(
            "/api/v1/sessions",
            json={
                "user_id": "teacher-cloud-policy",
                "course_id": "CT",
                "title": "星辰显式授权",
            },
        ).json()
        created = client.post(
            "/api/v1/tasks",
            json=_lesson_payload(session["id"], allow_cloud=True),
        )
        assert created.status_code == 202

        task_id = created.json()["id"]
        for _ in range(250):
            task = client.get(f"/api/v1/tasks/{task_id}").json()
            if task["status"] in {"completed", "failed", "cancelled"}:
                break
        else:
            raise AssertionError("task did not finish")

    assert task["status"] == "completed"
    assert provider.calls == ["TEACH_01_LESSON_PREP_V1"]
    assert task["result_content"]["provider"] == "xingchen"


def test_low_confidence_cloud_router_also_requires_explicit_authorization(
    settings: Settings,
) -> None:
    configured = _xingchen_settings(settings)
    router = TaskRouter(AgentRegistry(), configured)
    request = AgentRequest(
        session_id="session-cloud-router-policy",
        user_id="student-cloud-router-policy",
        scene="dispatch",
        course_id="AUTO",
        intent="unknown",
        canonical_input={"text": "帮我处理一下这个任务。"},
    )

    local_decision = router.route(request)
    cloud_decision = router.route(
        request.model_copy(update={"options": {"allow_cloud": True}})
    )

    assert local_decision.agent_id == "GENERAL_QUESTION_V1"
    assert local_decision.route_status.value == "selected"
    assert "cloud_router_not_authorized" in local_decision.reason_codes
    assert "general_question_fallback" in local_decision.reason_codes
    assert local_decision.cloud_router_invoked is False
    assert cloud_decision.agent_id == "ROUTER_01_FALLBACK_V1"
    assert cloud_decision.provider_required is True
    assert cloud_decision.cloud_router_invoked is True
