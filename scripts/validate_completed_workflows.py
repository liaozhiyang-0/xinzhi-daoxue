from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from app.agents import AgentRegistry  # noqa: E402
from app.contracts import AgentRequest  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.providers.xingchen import XingchenCloudProvider  # noqa: E402


def cases() -> dict[str, AgentRequest]:
    common = {
        "session_id": "workflow-contract-session",
        "user_id": "workflow-contract-user",
        "scene": "dispatch",
        "course_id": "CT",
    }
    return {
        "LEARN_01_KNOWLEDGE_QA_V1": AgentRequest(
            **common,
            intent="explain_concept",
            canonical_input={"text": "为什么电容电压不能突变？"},
            options={"request_id": "contract-learn", "response_depth": "brief"},
        ),
        "SOLVER_CT_V1": AgentRequest(
            **common,
            intent="solve_problem",
            canonical_input={"text": "10V理想电压源与5欧电阻串联，求回路电流。"},
            options={"request_id": "contract-solver"},
        ),
        "TEACH_01_LESSON_PREP_V1": AgentRequest(
            **common,
            user_role="teacher",
            intent="lesson_prep",
            canonical_input={
                "text": "为大二学生设计45分钟电容暂态课程，包含活动与作业。",
                "topic": "电容暂态",
                "student_level": "大二",
                "class_duration": "45分钟",
                "lesson_count": "1",
            },
            options={"request_id": "contract-lesson", "response_depth": "brief"},
        ),
        "TEACH_02_ASSIGNMENT_REVIEW_V1": AgentRequest(
            **common,
            user_role="teacher",
            intent="assignment_review",
            canonical_input={
                "text": "按给定rubric评阅以下合成作答，仅输出建议分。",
                "assignment_text": "10V电源串联5欧电阻，求电流。",
                "student_answer": "I=10/5=2A。",
                "reference_answer": "2A。",
                "rubric": "列式4分，结果与单位6分。",
                "maximum_score": "10",
            },
            options={"request_id": "contract-review", "response_depth": "brief"},
        ),
        "RESEARCH_02_ACADEMIC_WRITING_V1": AgentRequest(
            **common,
            user_role="researcher",
            intent="academic_writing",
            canonical_input={
                "text": "润色下面的合成示例句，不新增事实或引用。",
                "writing_task": "润色",
                "document_type": "结果段",
                "source_text": "在合成测试数据中，方案A的指标高于方案B。",
            },
            options={"request_id": "contract-writing"},
        ),
        "RESEARCH_03_DATA_ANALYSIS_V1": AgentRequest(
            **common,
            user_role="researcher",
            intent="data_analysis",
            canonical_input={
                "text": "为合成二分类数据设计分析计划，不宣称已运行计算。",
                "research_question": "比较两个合成分类方案",
                "data_description": "合成二分类数据；本请求未提供真实数值结果。",
                "analysis_goal": "生成分析计划",
            },
            options={"request_id": "contract-analysis"},
        ),
        "ROUTER_01_FALLBACK_V1": AgentRequest(
            **common,
            intent="unknown",
            canonical_input={"text": "这个任务边界模糊，请只选择一个目标工作流。"},
            options={
                "request_id": "contract-router",
                "available_agents": ["LEARN_01_KNOWLEDGE_QA_V1"],
                "candidate_agents": [
                    {"agent_id": "LEARN_01_KNOWLEDGE_QA_V1", "score": 0.55}
                ],
                "local_confidence": 0.55,
            },
        ),
    }


async def run(live: bool, selected_agents: set[str]) -> int:
    settings = Settings()
    registry = AgentRegistry()
    provider = XingchenCloudProvider(settings)
    report: list[dict[str, Any]] = []
    try:
        for agent_id, request in cases().items():
            if selected_agents and agent_id not in selected_agents:
                continue
            configured = registry.is_runtime_available(agent_id, settings)
            item: dict[str, Any] = {
                "agent_id": agent_id,
                "configured": configured,
                "executed": False,
            }
            if not live or not configured:
                item["status"] = "dry_run" if not live else "skipped_unavailable"
                report.append(item)
                continue
            started = perf_counter()
            try:
                result = await provider.run(agent_id, request, stream=False)
                item.update(
                    {
                        "executed": True,
                        "status": result.structured_result.get("status", "completed"),
                        "answer_nonempty": bool(result.answer.strip()),
                        "answer_length": len(result.answer),
                        "parse_status": result.structured_result.get(
                            "parse_status", "not_reported"
                        ),
                        "warnings": result.warnings,
                        "latency_ms": int((perf_counter() - started) * 1000),
                    }
                )
            except Exception as exc:
                item.update(
                    {
                        "executed": True,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "latency_ms": int((perf_counter() - started) * 1000),
                    }
                )
            report.append(item)
    finally:
        await provider.aclose()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(item["status"] != "failed" for item in report) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live", action="store_true", help="发送最小无隐私真实云端契约请求"
    )
    parser.add_argument(
        "--agent",
        action="append",
        choices=sorted(cases()),
        default=[],
        help="仅检查指定 Agent；可重复传入",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.live, set(args.agent)))


if __name__ == "__main__":
    raise SystemExit(main())
