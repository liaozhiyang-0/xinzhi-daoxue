from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    LearnerKnowledgeState,
    LearningActionRequest,
    LearningActionResponse,
    LearningFollowUpContext,
)
from app.core.errors import NotFoundError
from app.models.entities import (
    LearnerKnowledgeStateModel,
    LearningInteractionModel,
    PracticeAttemptModel,
    TaskModel,
    WrongAnswerRecordModel,
)
from app.services.practice_generation import PracticeGenerationService
from app.services.student_answer_review import StudentAnswerReviewService

DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[4] / "config" / "learning_mastery.yaml"
)


class LearningLoopService:
    def __init__(self, config_path: Path = DEFAULT_CONFIG) -> None:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.config = raw if isinstance(raw, dict) else {}
        self.reviewer = StudentAnswerReviewService()
        self.practice = PracticeGenerationService()

    async def act(
        self, session: AsyncSession, request: LearningActionRequest
    ) -> LearningActionResponse:
        previous = await session.scalar(
            select(LearningInteractionModel).where(
                LearningInteractionModel.user_id == request.user_id,
                LearningInteractionModel.idempotency_key == request.idempotency_key,
            )
        )
        if previous is not None:
            return LearningActionResponse.model_validate(previous.result)

        task = await session.get(TaskModel, request.source_task_id)
        if task is None or task.user_id != request.user_id:
            raise NotFoundError("未找到可访问的来源任务")
        structured = dict((task.result_content or {}).get("structured_result") or {})
        answer = str((task.result_content or {}).get("answer", ""))
        points = self._knowledge_points(structured)
        problem_summary = str(
            structured.get("problem_summary")
            or task.input_content.get("canonical_input", {}).get("text", "")
        )[:2000]
        if not points:
            points = ["本题涉及的核心概念"]
        interaction_id = uuid4().hex
        message = "学习动作已记录"
        follow_up = ""
        follow_up_intent = ""
        review = None
        practice = None
        states: list[LearnerKnowledgeStateModel] = []

        if request.action == "check_answer":
            review = self.reviewer.review(
                request.student_answer,
                reference_answer=str(structured.get("final_answer") or answer),
                reference_steps=list(structured.get("solution_steps") or []),
            )
            delta_name = {
                "correct": "correct_delta",
                "partially_correct": "partial_delta",
                "incorrect": "incorrect_delta",
                "insufficient": "hint_delta",
            }[review.status]
            states = await self._update_points(
                session,
                request.user_id,
                task.course_id,
                points,
                float(self.config[delta_name]),
                outcome=review.status,
            )
            message = "已按步骤对齐参考解并定位首个差异"
        elif request.action == "add_wrong_answer":
            states = await self._update_points(
                session,
                request.user_id,
                task.course_id,
                points,
                float(self.config["incorrect_delta"]),
                outcome="wrong_answer_saved",
            )
            session.add(
                WrongAnswerRecordModel(
                    source_task_id=task.id,
                    user_id=request.user_id,
                    course_id=task.course_id,
                    chapter=structured.get("chapter"),
                    knowledge_points=points,
                    problem_summary=problem_summary,
                    student_answer=request.student_answer,
                    error_types=[
                        str(item) for item in request.payload.get("error_types", [])
                    ],
                    feedback=dict(request.payload.get("feedback") or {}),
                    mastery_before=min(
                        1.0,
                        states[0].mastery_score - float(self.config["incorrect_delta"]),
                    ),
                    mastery_after=states[0].mastery_score,
                )
            )
            message = "已加入错题本并更新相关知识点状态"
        elif request.action == "mark_mastered":
            states = await self._update_points(
                session,
                request.user_id,
                task.course_id,
                points,
                float(self.config["mastered_delta"]),
                outcome="self_reported_mastered",
            )
            message = "已记录掌握状态；后续正确作答仍会继续校准"
        elif request.action == "get_hint":
            steps = list(structured.get("solution_steps") or [])
            if steps:
                message = "提示：先完成参考解的第一步结构化检查。"
                follow_up = self._follow_up_prompt(
                    task_id=task.id,
                    course_id=task.course_id,
                    problem_summary=problem_summary,
                    points=points,
                    instruction="只给出下一步提示，不要直接给最终答案。",
                )
            else:
                message = "当前结果缺少可提取步骤，将通过主任务链请求提示"
                follow_up = self._follow_up_prompt(
                    task_id=task.id,
                    course_id=task.course_id,
                    problem_summary=problem_summary,
                    points=points,
                    instruction="给出一个不泄露最终答案的分步提示。",
                )
            follow_up_intent = task.intent
            await self._update_points(
                session,
                request.user_id,
                task.course_id,
                points,
                float(self.config["hint_delta"]),
                outcome="hint_requested",
                hint=True,
            )
        elif request.action == "generate_variant":
            practice = self.practice.generate(task.id, problem_summary)
            if practice.status == "ready":
                session.add(
                    PracticeAttemptModel(
                        source_task_id=task.id,
                        user_id=request.user_id,
                        course_id=task.course_id,
                        problem=practice.model_dump(mode="json"),
                        reference_answer=practice.reference_answer,
                    )
                )
                message = "已生成并通过确定性可解性检查的变式题"
            else:
                follow_up = self._follow_up_prompt(
                    task_id=task.id,
                    course_id=task.course_id,
                    problem_summary=problem_summary,
                    points=points,
                    instruction=(
                        "生成一道同知识点变式题；先检查条件完整、可解性、单位和"
                        "参考答案唯一性，再展示题目。"
                    ),
                )
                follow_up_intent = task.intent
                message = "本地确定性生成器不支持该题型，将交回主任务链"
        else:
            follow_up = self._follow_up_prompt(
                task_id=task.id,
                course_id=task.course_id,
                problem_summary=problem_summary,
                points=points,
                instruction=(
                    "围绕原题讲解关联知识：先提炼核心概念，再说明概念之间的关系，"
                    "最后结合原题指出容易混淆和可迁移的判断方法。不要要求用户重新"
                    "提供题目背景。"
                ),
            )
            follow_up_intent = "explain_concept"
            message = "关联知识请求将通过统一任务主链执行"

        status: Literal["completed", "accepted", "needs_task"] = (
            "needs_task" if follow_up else "completed"
        )
        response = LearningActionResponse(
            interaction_id=interaction_id,
            action=request.action,
            status=status,
            message=message,
            follow_up_prompt=follow_up,
            follow_up_context=(
                LearningFollowUpContext(
                    source_task_id=task.id,
                    course_id=task.course_id,
                    intent=follow_up_intent,
                    action=request.action,
                )
                if follow_up
                else None
            ),
            review=review,
            practice=practice,
            mastery=[self._contract(item) for item in states],
        )
        session.add(
            LearningInteractionModel(
                id=interaction_id,
                source_task_id=task.id,
                user_id=request.user_id,
                action=request.action,
                idempotency_key=request.idempotency_key,
                payload={
                    **request.payload,
                    "student_answer": request.student_answer,
                },
                result=response.model_dump(mode="json"),
            )
        )
        await session.commit()
        return response

    @staticmethod
    def _knowledge_points(structured: dict[str, object]) -> list[str]:
        candidates: list[object] = []
        for field in ("knowledge_points", "key_points", "related_chapters"):
            value = structured.get(field)
            if isinstance(value, list):
                candidates.extend(value)
        retrieval_summary = structured.get("core_retrieval_summary")
        if isinstance(retrieval_summary, list):
            for item in retrieval_summary:
                if isinstance(item, dict):
                    candidates.extend((item.get("chapter"), item.get("title")))
        points: list[str] = []
        for item in candidates:
            value = str(item or "").strip()
            if not value or value == "UNKNOWN" or value in points:
                continue
            points.append(value[:120])
            if len(points) >= 6:
                break
        return points

    @staticmethod
    def _follow_up_prompt(
        *,
        task_id: str,
        course_id: str,
        problem_summary: str,
        points: list[str],
        instruction: str,
    ) -> str:
        source_problem = problem_summary.strip() or "来源任务未保存可读题面"
        point_text = "、".join(points)
        return (
            f"这是课程 {course_id} 中来源任务 {task_id} 的连续学习请求。\n"
            f"原题：\n{source_problem}\n\n"
            f"已识别的关联章节或知识点：{point_text}。\n"
            f"要求：{instruction}"
        )[:4000]

    async def list_states(
        self, session: AsyncSession, user_id: str, course_id: str | None = None
    ) -> list[LearnerKnowledgeState]:
        statement = select(LearnerKnowledgeStateModel).where(
            LearnerKnowledgeStateModel.user_id == user_id
        )
        if course_id:
            statement = statement.where(
                LearnerKnowledgeStateModel.course_id == course_id
            )
        rows = (await session.scalars(statement)).all()
        return [self._contract(item) for item in rows]

    async def _update_points(
        self,
        session: AsyncSession,
        user_id: str,
        course_id: str,
        points: list[str],
        delta: float,
        *,
        outcome: str,
        hint: bool = False,
    ) -> list[LearnerKnowledgeStateModel]:
        output: list[LearnerKnowledgeStateModel] = []
        for point in points:
            state = await session.scalar(
                select(LearnerKnowledgeStateModel).where(
                    LearnerKnowledgeStateModel.user_id == user_id,
                    LearnerKnowledgeStateModel.course_id == course_id,
                    LearnerKnowledgeStateModel.knowledge_point == point,
                )
            )
            if state is None:
                state = LearnerKnowledgeStateModel(
                    user_id=user_id,
                    course_id=course_id,
                    knowledge_point=point,
                    mastery_score=float(self.config["initial_score"]),
                    confidence=float(self.config["initial_confidence"]),
                    correct_count=0,
                    incorrect_count=0,
                    hint_count=0,
                    evidence={},
                )
                session.add(state)
            state.mastery_score = max(0.0, min(1.0, state.mastery_score + delta))
            state.confidence = min(
                1.0, state.confidence + float(self.config["confidence_step"])
            )
            if hint:
                state.hint_count += 1
            elif delta > 0:
                state.correct_count += 1
            elif delta < 0:
                state.incorrect_count += 1
            state.evidence = {**state.evidence, "last_outcome": outcome}
            output.append(state)
        await session.flush()
        return output

    @staticmethod
    def _contract(item: LearnerKnowledgeStateModel) -> LearnerKnowledgeState:
        return LearnerKnowledgeState(
            course_id=item.course_id,
            knowledge_point=item.knowledge_point,
            mastery_score=item.mastery_score,
            confidence=item.confidence,
            correct_count=item.correct_count,
            incorrect_count=item.incorrect_count,
            hint_count=item.hint_count,
        )
