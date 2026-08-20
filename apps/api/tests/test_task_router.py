from dataclasses import replace

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AttachmentRef, Intent, RouteStatus
from app.core.config import Settings


def request(course_id: str, intent: str) -> AgentRequest:
    return AgentRequest.model_validate(
        {
            "session_id": "session-route",
            "user_id": "user-route",
            "scene": "learning",
            "course_id": course_id,
            "intent": intent,
            "canonical_input": {"question": "测试问题"},
        }
    )


@pytest.mark.parametrize("course_id", ["CT", "AE", "DE", "SS", "DSP", "COMM"])
@pytest.mark.parametrize("intent", ["general_qa", "explain_concept"])
def test_learning_routes_to_local_knowledge_agent(course_id: str, intent: str) -> None:
    decision = TaskRouter(AgentRegistry()).route(request(course_id, intent))

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "LEARN_01_KNOWLEDGE_QA_V1"
    assert decision.retrieval_required is True
    assert decision.provider_required is False
    assert decision.route_source == "local_fast"
    assert decision.original_agent_id is None
    assert decision.fallback_used is False


def test_ct_solve_routes_to_solver() -> None:
    decision = TaskRouter(AgentRegistry()).route(request("CT", "solve_problem"))

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.provider_required is False


def test_legacy_allow_cloud_flag_cannot_enable_remote_routing() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-route",
            "user_id": "user-route",
            "scene": "learning",
            "course_id": "CT",
            "intent": "explain_concept",
            "canonical_input": {"question": "测试问题"},
            "options": {"allow_cloud": True},
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert "allow_cloud" not in task_request.options
    assert decision.agent_id == "LEARN_01_KNOWLEDGE_QA_V1"
    assert decision.provider_required is False
    assert decision.route_source == "local_fast"


def test_explicit_course_unknown_learning_question_routes_to_course_knowledge() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-route",
            "user_id": "user-route",
            "scene": "learning",
            "course_id": "AE",
            "intent": "unknown",
            "canonical_input": {
                "text": (
                    "请解释负反馈为什么能改善放大器性能，并引用模拟电子技术课程资料。"
                )
            },
            "options": {"use_local_rag": True},
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "LEARN_01_KNOWLEDGE_QA_V1"
    assert decision.intent == "explain_concept"
    assert decision.course_id == "AE"
    assert decision.retrieval_required is True
    assert decision.route_source == "local_course_context"
    assert "explicit_course_learning_context" in decision.reason_codes



def test_disabled_local_agent_is_not_kept_by_local_only_routing() -> None:
    registry = AgentRegistry()
    primary = registry.get("ACADEMIC_PROBLEM_SOLVER")
    registry._agents[primary.agent_id] = replace(
        primary,
        provider="local",
        enabled=False,
        publication_status="published",
        execution_mode="local",
        route_when_unconfigured=True,
    )

    decision = TaskRouter(registry, Settings(_env_file=None)).route(
        request("CT", "solve_problem").model_copy(
            update={"options": {}}
        )
    )

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "GENERAL_MODEL_FALLBACK_V1"
    assert decision.fallback_used is True
    assert decision.agent_id != primary.agent_id


@pytest.mark.parametrize(
    ("intent", "agent_id"),
    [
        ("academic_writing", "RESEARCH_02_ACADEMIC_WRITING_V1"),
        ("data_analysis", "RESEARCH_03_DATA_ANALYSIS_V1"),
    ],
)
def test_explicit_research_intent_routes_to_declared_agent(
    intent: str, agent_id: str
) -> None:
    decision = TaskRouter(AgentRegistry()).route(request("CT", intent))

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == agent_id
    assert decision.intent == intent
    assert decision.retrieval_required is False
    assert decision.provider_required is False


def test_data_analysis_accepts_tabular_attachment_input() -> None:
    task_request = request("CT", "data_analysis").model_copy(
        update={
            "canonical_input": {"text": "比较两组 score 的差异"},
            "attachments": [
                AttachmentRef(
                    file_id="file-analysis-csv",
                    filename="experiment.csv",
                    content_type="text/csv",
                    size_bytes=128,
                    storage_key="local:experiment.csv",
                )
            ],
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"


def test_text_document_attachment_remains_text_compatible() -> None:
    task_request = request("CT", "solve_problem").model_copy(
        update={
            "attachments": [
                AttachmentRef(
                    file_id="file-note",
                    filename="task-note.txt",
                    content_type="text/plain",
                    size_bytes=32,
                    storage_key="local:task-note.txt",
                    ingestion_status="ready",
                    extracted_text="已解析的题目补充说明",
                )
            ]
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"


def test_research_analysis_v2_stays_local_without_model_keys() -> None:
    task_request = request("CT", "data_analysis").model_copy(
        update={
            "canonical_input": {
                "text": "比较 treatment 与 control 的 score 差异，并报告效应量"
            },
            "options": {
                "research_analysis_v2": {"execute": True},
                "scenario_agent_id": "RESEARCH_03_DATA_ANALYSIS_V1",
                "_scenario_catalog_bound": True,
            },
        }
    )
    settings = Settings(
        _env_file=None,
        default_agent_provider="mock",
        iflytek_spark_api_key="",
        dashscope_api_key="",
    )

    decision = TaskRouter(AgentRegistry(), settings).route(task_request)

    assert decision.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
    assert decision.fallback_used is False
    assert decision.provider_required is False


def test_bound_scenario_selects_declared_agent_before_keyword_routing() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-scenario",
            "user_id": "user-scenario",
            "scene": "teaching",
            "course_id": "CT",
            "intent": "lesson_prep",
            "canonical_input": {"text": "璇峰府鎴戝噯澶囦竴鑺傝"},
            "options": {
                "scenario_id": "faculty_course_copilot_v1",
                "scenario_agent_id": "TEACH_01_LESSON_PREP_V1",
                "_scenario_catalog_bound": True,
            },
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "TEACH_01_LESSON_PREP_V1"
    assert decision.route_source == "scenario_catalog"
    assert "scenario_catalog_bound" in decision.reason_codes


def test_admin_debug_override_wins_before_research_intent_recognition() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-debug-override",
            "user_id": "user-debug-override",
            "user_role": "admin",
            "course_id": "UNKNOWN",
            "intent": "general_qa",
            "canonical_input": {"question": "请解释数据结构中的栈。"},
            "options": {"debug_agent_id": "GENERAL_QUESTION_V1"},
        }
    )

    decision = TaskRouter(
        AgentRegistry(), Settings(_env_file=None, app_env="development")
    ).route(task_request)

    assert decision.agent_id == "GENERAL_QUESTION_V1"
    assert decision.route_source == "admin_debug_override"


def test_latest_paper_request_routes_to_dedicated_academic_search() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-paper-search",
            "user_id": "user-paper-search",
            "scene": "research",
            "course_id": "CT",
            "intent": "unknown",
            "canonical_input": {
                "text": "帮我查找最新的电子信息领域相关论文，并提供链接和摘要"
            },
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.reason_codes[-1] == "academic_search_request"
    assert decision.provider_required is False


def test_unsupported_image_input_returns_unresolved_route_instead_of_raising() -> None:
    task_request = AgentRequest(
        session_id="session-paper-image",
        user_id="user-paper-image",
        scene="research",
        course_id="AUTO",
        intent=Intent.ACADEMIC_SEARCH,
        canonical_input={
            "text": "\u68c0\u7d22\u8fd9\u5f20\u56fe\u7247\u76f8\u5173\u7684\u8bba\u6587"
        },
        attachments=[
            AttachmentRef(
                file_id="image-1",
                filename="figure.png",
                content_type="image/png",
                size_bytes=1,
                storage_key="local/image-1",
            )
        ],
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "UNRESOLVED"
    assert decision.route_status == RouteStatus.UNRESOLVED
    assert "target_input_unsupported" in decision.reason_codes


def test_explicit_assignment_review_preflights_image_capability() -> None:
    task_request = request("CT", "assignment_review").model_copy(
        update={
            "canonical_input": {
                "text": "\u8bf7\u6279\u6539\u5b66\u751f\u7b54\u6848"
            },
            "attachments": [
                AttachmentRef(
                    file_id="image-assignment",
                    filename="answer.png",
                    content_type="image/png",
                    size_bytes=1,
                    storage_key="local/answer.png",
                )
            ],
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.route_status == RouteStatus.UNRESOLVED
    assert decision.agent_id == "UNRESOLVED"
    assert "target_input_unsupported" in decision.reason_codes


def test_writing_request_stays_on_academic_writing_agent() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-paper-writing",
            "user_id": "user-paper-writing",
            "scene": "research",
            "course_id": "CT",
            "intent": "unknown",
            "canonical_input": {"text": "请把这段内容改写成论文摘要"},
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_02_ACADEMIC_WRITING_V1"


def test_research_intent_wins_over_unspecified_course_fallback() -> None:
    task_request = AgentRequest(
        session_id="session-research-auto-course",
        user_id="user-research-auto-course",
        course_id="AUTO",
        intent="unknown",
        canonical_input={
            "text": (
                "\u0032\u0030\u0032\u0034\u5e74\u81f3\u0032\u0030\u0032\u0036\u5e74"
                "\u67d4\u6027\u7535\u5b50\u7535\u5b50\u76ae\u80a4\u6709\u54ea\u4e9b"
                "\u4ee3\u8868\u6027\u8fdb\u5c55\uff1f"
            )
        },
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.intent == "academic_search"
    assert decision.intent_recognition["task_family"] == "research"


@pytest.mark.parametrize(
    ("text", "agent_id", "intent"),
    [
        (
            "请分析以下数据的平均值、最大值和趋势：1, 2, 3, 5, 8",
            "RESEARCH_03_DATA_ANALYSIS_V1",
            "data_analysis",
        ),
        (
            "请把这句话改写成学术中文：柔性传感器能够感知人体运动。",
            "RESEARCH_02_ACADEMIC_WRITING_V1",
            "academic_writing",
        ),
    ],
)
def test_high_confidence_recognized_workflow_bypasses_keyword_solver(
    text: str, agent_id: str, intent: str
) -> None:
    task_request = AgentRequest(
        session_id="session-recognized-workflow",
        user_id="user-recognized-workflow",
        course_id="AUTO",
        intent="unknown",
        canonical_input={"text": text},
        options={},
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == agent_id
    assert decision.intent == intent
    assert decision.route_source == "local_intent_recognition"
    assert f"recognized_intent:{intent}" in decision.reason_codes


def test_network_follow_up_does_not_inherit_previous_course_context() -> None:
    task_request = AgentRequest(
        session_id="session-network-follow-up",
        user_id="user-network-follow-up",
        course_id="AUTO",
        intent="unknown",
        canonical_input={"text": "那为什么服务器要回复 SYN+ACK？"},
        options={
            "previous_agent": "LEARN_01_KNOWLEDGE_QA_V1",
            "previous_intent": "explain_concept",
        },
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "GENERAL_QUESTION_V1"
    assert decision.course_id == "UNKNOWN"
    assert decision.intent == "general_qa"
    assert "topic_outside_course" in decision.reason_codes


def test_research_follow_up_preserves_unknown_previous_course() -> None:
    task_request = AgentRequest(
        session_id="session-research-follow-up-course",
        user_id="user-research-follow-up-course",
        course_id="UNKNOWN",
        intent="academic_search",
        canonical_input={
            "text": "其中哪些进展已经有产品化迹象？请按多模态和智能体分别说明。"
        },
        options={
            "previous_agent": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "previous_intent": "academic_search",
            "previous_task_family": "research",
            "previous_course": "UNKNOWN",
            "previous_external_query": (
                "2024年至2026年生成式人工智能在多模态和智能体方面有哪些代表性进展？"
            ),
        },
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.course_id == "UNKNOWN"


def test_research_workflow_does_not_inherit_learning_session_course() -> None:
    task_request = AgentRequest(
        session_id="session-research-course-boundary",
        user_id="user-research-course-boundary",
        course_id="AUTO",
        intent=Intent.ACADEMIC_SEARCH,
        canonical_input={"text": "检索近五年关于主动学习对工程教育效果的学术证据。"},
        options={
            "active_course": "CT",
            "previous_course": "CT",
        },
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.course_id == "UNKNOWN"
    assert "research_workflow_neutral_course" in decision.reason_codes


def test_cross_domain_topic_overrides_stale_explicit_course_hint() -> None:
    task_request = AgentRequest(
        session_id="session-cross-domain-hint",
        user_id="user-cross-domain-hint",
        course_id="CT",
        intent="unknown",
        canonical_input={"text": "2024年至2026年人工智能有哪些代表性进展？"},
        options={},
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.course_id == "UNKNOWN"
    assert "course_hint_overridden" in decision.reason_codes


def test_search_request_with_requested_abstract_is_not_writing() -> None:
    task_request = AgentRequest(
        session_id="session-research-abstract",
        user_id="user-research-abstract",
        course_id="AUTO",
        intent="unknown",
        canonical_input={
            "text": (
                "\u8bf7\u67e5\u627e\u6700\u65b0\u7684\u67d4\u6027\u7535\u5b50\u8bba\u6587\uff0c"
                "\u5e76\u63d0\u4f9b\u6458\u8981"
            )
        },
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.intent == "academic_search"


def test_dynamic_circuit_state_variables_do_not_route_to_data_analysis() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-dynamic-circuit",
            "user_id": "user-dynamic-circuit",
            "scene": "dispatch",
            "course_id": "CT",
            "intent": "unknown",
            "canonical_input": {
                "text": (
                    "含受控源的二阶动态电路，以v(t)和iL(t)为状态变量，"
                    "求换路初始条件，建立状态方程和二阶微分方程，求完整响应、"
                    "自然频率、阻尼类型、第一次经过零点的时刻并验证能量平衡。"
                )
            },
            "options": {},
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.intent == "solve_problem"
    assert decision.provider_required is False
    assert "domain_contract:dynamic_circuit_problem" in decision.reason_codes
    data_candidate = next(
        item
        for item in decision.candidate_agents
        if item.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
    )
    assert data_candidate.score == 0.0


@pytest.mark.parametrize(
    "text",
    [
        "已知电阻电压 u=10V、电流 i=2A，按关联参考方向求吸收功率。",
        "求端口等效电阻。",
        "判断二极管当前工作状态。",
        "计算放大电路的电压增益。",
        "化简逻辑式并给出真值表。",
        "求离散系统的卷积响应。",
    ],
)
def test_natural_academic_problem_language_routes_to_solver(text: str) -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-natural-problem",
            "user_id": "user-natural-problem",
            "scene": "learning",
            "course_id": "CT",
            "intent": "general_qa",
            "canonical_input": {"text": text},
            "options": {},
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.intent == "solve_problem"
    assert "domain_contract:academic_problem_language" in decision.reason_codes


@pytest.mark.parametrize(
    ("course_id", "text"),
    [
        ("DSP", "求离散系统的卷积响应 x[n] 和 h[n]。"),
        ("COMM", "求通信系统的误码率。"),
        ("EM", "求电磁场中某点的电场强度。"),
        ("EMBEDDED", "设计单片机定时器并求中断周期。"),
    ],
)
def test_explicit_course_problem_bypasses_knowledge_route(
    course_id: str, text: str
) -> None:
    task_request = AgentRequest(
        session_id="session-cross-course-problem",
        user_id="user-cross-course-problem",
        scene="dispatch",
        course_id=course_id,
        intent="unknown",
        canonical_input={"text": text},
        options={},
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.course_id == course_id
    assert decision.intent == "solve_problem"
    assert decision.route_source == "local_solver_contract"


@pytest.mark.parametrize(
    ("text", "course_id"),
    [
        ("已知采样频率，求信号频谱。", "DSP"),
        ("化简逻辑式并给出真值表。", "DE"),
        ("求电场强度。", "EM"),
    ],
)
def test_auto_course_problem_is_inferred_before_solver_execution(
    text: str, course_id: str
) -> None:
    task_request = AgentRequest(
        session_id="session-auto-course-problem",
        user_id="user-auto-course-problem",
        scene="dispatch",
        course_id="AUTO",
        intent="unknown",
        canonical_input={"text": text},
        options={},
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.course_id == course_id
    assert decision.intent == "solve_problem"
    assert "professional_solver_contract" in decision.reason_codes


def test_solver_contract_is_not_overridden_by_second_route_pass() -> None:
    task_request = AgentRequest(
        session_id="session-solver-route-lock",
        user_id="user-solver-route-lock",
        scene="dispatch",
        course_id="DSP",
        intent="unknown",
        canonical_input={"text": "求离散系统的卷积响应。"},
        options={},
    )
    router = TaskRouter(AgentRegistry())
    decision = router.route(task_request)

    assert decision.route_confidence < 0.80
    assert router.overall_refinement_allowed(decision) is False


def test_general_question_problem_submission_completes_with_solver_answer(
    api, client
) -> None:
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        intent="general_qa",
        options={"use_local_rag": False},
    )
    payload["canonical_input"] = {
        "text": "已知电阻电压 u=10V、电流 i=2A，按关联参考方向求吸收功率。"
    }

    response = client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 202
    task = api.wait_for_task(response.json()["id"], timeout=15)
    assert task["status"] == "completed"
    assert task["agent_id"] == "ACADEMIC_PROBLEM_SOLVER"
    assert task["intent"] == "solve_problem"
    assert task["result_content"]["answer"].strip()
