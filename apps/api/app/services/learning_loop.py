from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentEventType, SolutionPacketV1
from app.contracts.learning import (
    FeedbackUptakeV1,
    HintDecisionV1,
    LearnerKnowledgeState,
    LearningActionRequest,
    LearningActionResponse,
    LearningFollowUpContext,
    LearningRuntimeNodeStatusRead,
    LearningRuntimeStatusRead,
    StudentAttempt,
    TeachingMode,
    VerificationReportV1,
)
from app.core.errors import ConflictError, NotFoundError
from app.models.entities import (
    LearnerKnowledgeStateModel,
    LearningInteractionModel,
    PracticeAttemptModel,
    TaskModel,
    WrongAnswerRecordModel,
)
from app.repositories import AgentRunRepository
from app.repositories.learning import LearningRecordRepository
from app.services.answer_disclosure import INTERNAL_TEACHING_KEY
from app.services.event_service import append_task_event
from app.services.feedback_uptake import FeedbackUptakeService
from app.services.learning_outcome import LearningOutcomeService
from app.services.learning_progress_runtime import (
    LearningProgressRuntimeService,
)
from app.services.practice_generation import PracticeGenerationService
from app.services.retest_plans import RetestPlanService
from app.services.session_working_state import SessionWorkingStateService
from app.services.student_answer_review import StudentAnswerReviewService
from app.services.student_attempts import StudentAttemptService
from app.services.student_verification import StudentVerificationService
from app.services.teaching_interaction import (
    PHASE2_ACTIONS,
    TeachingInteractionService,
)
from app.services.teaching_interaction_runtime import (
    TeachingInteractionRuntimeService,
)

DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[4] / "config" / "learning_mastery.yaml"
)
PHASE3_ACTIONS = frozenset(
    {
        "submit_attempt_revision",
        "start_retest",
        "complete_retest",
        "dismiss_retest",
    }
)


class LearningLoopService:
    def __init__(
        self,
        config_path: Path = DEFAULT_CONFIG,
        teaching_interactions: TeachingInteractionService | None = None,
        teaching_interaction_runtime: TeachingInteractionRuntimeService | None = None,
        learning_progress_runtime: LearningProgressRuntimeService | None = None,
        learning_outcome: LearningOutcomeService | None = None,
    ) -> None:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.config = raw if isinstance(raw, dict) else {}
        self.reviewer = StudentAnswerReviewService()
        self.practice = PracticeGenerationService()
        self.teaching_interactions = teaching_interactions
        self.teaching_interaction_runtime = teaching_interaction_runtime
        self.learning_progress_runtime = learning_progress_runtime
        self.attempts = StudentAttemptService()
        self.feedback_uptake = FeedbackUptakeService()
        self.verifier = StudentVerificationService()
        self.learning_outcome = learning_outcome or LearningOutcomeService(config_path)
        self.retests: RetestPlanService = self.learning_outcome.retests

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
        interaction_id = uuid4().hex
        if request.action in PHASE3_ACTIONS:
            if (
                self.learning_progress_runtime is not None
                and self.learning_progress_runtime.supports(request)
            ):
                progress_outcome = await self.learning_progress_runtime.execute(
                    session,
                    task,
                    request,
                    interaction_id=interaction_id,
                )
                response = progress_outcome.response.model_copy(
                    update={
                        "status": (
                            "accepted"
                            if progress_outcome.status == "waiting_approval"
                            else progress_outcome.response.status
                        ),
                        "runtime_run_id": progress_outcome.run_id,
                        "runtime_status": progress_outcome.status,
                        "approval_required": progress_outcome.approval_required,
                    }
                )
                await self._persist_interaction(
                    session, task, request, response
                )
                return response
            return await self._act_phase3(session, task, request, interaction_id)
        if (
            request.action in PHASE2_ACTIONS
            and self.teaching_interaction_runtime is not None
            and self.teaching_interaction_runtime.supports(request)
        ):
            teaching_outcome = await self.teaching_interaction_runtime.execute(
                session,
                task,
                request,
                interaction_id=interaction_id,
            )
            response = LearningActionResponse(
                interaction_id=interaction_id,
                action=request.action,
                status=(
                    "accepted"
                    if teaching_outcome.status == "waiting_approval"
                    else "completed"
                ),
                message=teaching_outcome.message,
                teaching=teaching_outcome.teaching,
                runtime_run_id=teaching_outcome.run_id,
                runtime_status=teaching_outcome.status,
                approval_required=teaching_outcome.approval_required,
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
        if request.action in PHASE2_ACTIONS and self.teaching_interactions is not None:
            message, teaching = await self.teaching_interactions.act(
                session,
                task,
                request,
            )
            response = LearningActionResponse(
                interaction_id=interaction_id,
                action=request.action,
                status="completed",
                message=message,
                teaching=teaching,
            )
            session.add(
                LearningInteractionModel(
                    id=response.interaction_id,
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

    async def _persist_interaction(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
        response: LearningActionResponse,
    ) -> None:
        session.add(
            LearningInteractionModel(
                id=response.interaction_id,
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

    async def approve_runtime_interaction(
        self,
        session: AsyncSession,
        run_id: str,
        *,
        user_id: str,
        expected_state_version: int | None = None,
    ) -> LearningActionResponse:
        model = await AgentRunRepository(session).get(run_id, for_update=True)
        if model is None:
            raise NotFoundError("teaching interaction Runtime run not found")
        task = await session.get(TaskModel, model.task_id)
        if task is None or (user_id and task.user_id != user_id):
            raise NotFoundError("teaching interaction Runtime run not found")
        runtime: (
            TeachingInteractionRuntimeService | LearningProgressRuntimeService
        )
        if (
            self.teaching_interaction_runtime is not None
            and model.run_kind == self.teaching_interaction_runtime.run_kind
        ):
            runtime = self.teaching_interaction_runtime
        elif (
            self.learning_progress_runtime is not None
            and model.run_kind == self.learning_progress_runtime.run_kind
        ):
            runtime = self.learning_progress_runtime
        else:
            raise NotFoundError("learning Runtime run not found")
        try:
            outcome: Any = await runtime.approve(
                session,
                run_id,
                user_id=task.user_id,
                expected_state_version=expected_state_version,
            )
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        interaction = await session.get(
            LearningInteractionModel, outcome.interaction_id
        )
        if interaction is None:
            candidates = await session.scalars(
                select(LearningInteractionModel).where(
                    LearningInteractionModel.source_task_id == task.id,
                    LearningInteractionModel.user_id == task.user_id,
                )
            )
            interaction = next(
                (
                    item
                    for item in candidates
                    if item.result.get("runtime_run_id") == run_id
                ),
                None,
            )
        if interaction is None or (user_id and interaction.user_id != user_id):
            raise ConflictError("teaching interaction result is missing")
        response = LearningActionResponse.model_validate(interaction.result)
        runtime_response = getattr(outcome, "response", None)
        response = response.model_copy(
            update={
                "status": "completed",
                "runtime_status": outcome.status,
                "approval_required": False,
                "message": (
                    getattr(outcome, "message", "") or response.message
                ),
                "teaching": (
                    getattr(outcome, "teaching", {}) or response.teaching
                ),
                "attempt": (
                    runtime_response.attempt
                    if runtime_response is not None and runtime_response.attempt
                    else response.attempt
                ),
                "feedback_uptake": (
                    runtime_response.feedback_uptake
                    if runtime_response is not None
                    and runtime_response.feedback_uptake is not None
                    else response.feedback_uptake
                ),
                "mastery": (
                    runtime_response.mastery
                    if runtime_response is not None and runtime_response.mastery
                    else response.mastery
                ),
                "mastery_evidence": (
                    runtime_response.mastery_evidence
                    if runtime_response is not None
                    and runtime_response.mastery_evidence
                    else response.mastery_evidence
                ),
                "retest_plans": (
                    runtime_response.retest_plans
                    if runtime_response is not None
                    and runtime_response.retest_plans
                    else response.retest_plans
                ),
            }
        )
        interaction.result = response.model_dump(mode="json")
        await append_task_event(
            session,
            task.id,
            AgentEventType.AGENT_PROGRESS,
            agent_id=runtime.agent_id,
            data={
                "stage_id": "teaching_runtime_control",
                "status": "approval_granted",
                "runtime_run_id": run_id,
                "state_version": model.state_version,
            },
        )
        await session.commit()
        return response

    async def runtime_status(
        self,
        session: AsyncSession,
        run_id: str,
        *,
        user_id: str,
    ) -> LearningRuntimeStatusRead:
        """Return a redacted, ownership-checked LearningLoop checkpoint."""

        repository = AgentRunRepository(session)
        model = await repository.get(run_id)
        if model is None or model.run_kind not in {
            "teaching_interaction",
            "learning_progress",
        }:
            raise NotFoundError("learning Runtime run not found")
        task = await session.get(TaskModel, model.task_id)
        if task is None or (user_id and task.user_id != user_id):
            raise NotFoundError("learning Runtime run not found")
        run = await repository.restore(run_id)
        if run is None:
            raise NotFoundError("learning Runtime checkpoint not found")
        goal = run.goal_contract or run.plan.goal_contract
        if goal is None:
            raise NotFoundError("learning Runtime goal contract not found")
        node_statuses = [
            LearningRuntimeNodeStatusRead(
                node_id=node.node_id,
                status=run.nodes[node.node_id].status.value,
                effect_status=run.nodes[node.node_id].effect_status.value,
                attempt=run.nodes[node.node_id].attempt,
                error_code=run.nodes[node.node_id].error_code,
            )
            for node in run.plan.nodes
        ]
        status = run.status.value
        return LearningRuntimeStatusRead(
            run_id=run.run_id,
            task_id=run.task_id,
            runtime_id=model.agent_id,
            run_kind=model.run_kind,
            status=status,
            state_version=run.state_version,
            goal=run.goal,
            success_criteria=list(goal.success_criteria),
            required_capabilities=list(goal.required_capabilities),
            goal_source=goal.source,
            node_statuses=node_statuses,
            available_controls=(
                ["approve"] if status == "waiting_approval" else []
            ),
            approval_required=status == "waiting_approval",
            resumable=status in {"paused", "waiting_input", "waiting_approval"},
        )

    async def execute_phase3_action(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
        interaction_id: str,
    ) -> LearningActionResponse:
        """Execute the legacy phase-3 policy inside a Runtime apply node."""

        return await self._act_phase3(
            session,
            task,
            request,
            interaction_id,
            persist_interaction=False,
        )

    async def _act_phase3(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
        interaction_id: str,
        *,
        persist_interaction: bool = True,
    ) -> LearningActionResponse:
        response: LearningActionResponse
        if request.action == "submit_attempt_revision":
            response = await self._submit_attempt_revision(
                session, task, request, interaction_id
            )
        elif request.action == "start_retest":
            plan_id = str(request.payload.get("retest_plan_id", ""))
            plan, practice = await self.retests.start(
                session,
                retest_plan_id=plan_id,
                user_id=request.user_id,
            )
            instruction = (
                practice.problem_text
                if practice.status == "ready"
                else (
                    f"围绕知识点 {plan.skill_id} 给出一道不含答案的受控微测题；"
                    "无法确定性生成时只解释暂不支持，不得虚构答案键。"
                )
            )
            response = LearningActionResponse(
                interaction_id=interaction_id,
                action=request.action,
                status="needs_task",
                message="复习题已准备；请通过普通任务链开始作答",
                follow_up_prompt=instruction,
                follow_up_context=LearningFollowUpContext(
                    source_task_id=plan.source_task_id,
                    course_id=task.course_id,
                    intent=task.intent,
                    action=request.action,
                ),
                practice=practice,
                retest_plans=[self.retests.to_contract(plan)],
            )
        elif request.action == "dismiss_retest":
            plan = await self.retests.dismiss(
                session,
                retest_plan_id=str(request.payload.get("retest_plan_id", "")),
                user_id=request.user_id,
            )
            response = LearningActionResponse(
                interaction_id=interaction_id,
                action=request.action,
                status="completed",
                message="已将该复习项设为稍后处理",
                retest_plans=[self.retests.to_contract(plan)],
            )
        else:
            response = await self._complete_retest(
                session, task, request, interaction_id
            )
        if persist_interaction:
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

    async def _submit_attempt_revision(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
        interaction_id: str,
    ) -> LearningActionResponse:
        raw_attempt = request.payload.get("attempt")
        attempt_payload = dict(raw_attempt) if isinstance(raw_attempt, dict) else {}
        if not attempt_payload:
            attempt_payload = {
                "raw_text": request.student_answer,
                "final_answer": request.payload.get("final_answer"),
                "steps": request.payload.get("steps", []),
                "confidence": request.payload.get("confidence"),
            }
        student_attempt = StudentAttempt.model_validate(attempt_payload)
        working = await SessionWorkingStateService(session).get(task.session_id)
        teaching_state = working.teaching_state
        packet, report, hint = self._phase3_context(task, student_attempt)
        previous_id = str(
            request.payload.get("revision_of_attempt_id")
            or (teaching_state.current_attempt_id if teaching_state else "")
            or ""
        )
        attempt_save_started = perf_counter()
        model = await self.attempts.create(
            session,
            task=task,
            user_id=request.user_id,
            idempotency_key=f"{request.idempotency_key}:attempt",
            attempt=student_attempt,
            revision_of_attempt_id=previous_id or None,
            teaching_mode=(
                teaching_state.teaching_mode
                if teaching_state
                else TeachingMode.CHECK_MY_WORK
            ),
            hint_level_used=(
                teaching_state.current_hint_level if teaching_state else None
            ),
            full_solution_seen=bool(
                teaching_state and teaching_state.full_solution_disclosed
            ),
            verification_report=report.model_dump(mode="json"),
        )
        attempt_save_ms = (perf_counter() - attempt_save_started) * 1000
        uptake: FeedbackUptakeV1 | None = None
        uptake_ms = 0.0
        if model.revision_of_attempt_id:
            previous = await self.attempts.get(
                session,
                attempt_id=model.revision_of_attempt_id,
                user_id=request.user_id,
            )
            previous_model = await LearningRecordRepository(session).attempt_by_id(
                previous.attempt_id, request.user_id
            )
            assert previous_model is not None
            uptake, uptake_ms = self.feedback_uptake.evaluate(
                previous=previous_model,
                current=model,
                hint=hint,
            )
            model.feedback_uptake = uptake.model_dump(mode="json")
        skill_ids = list(packet.skill_ids) if packet else []
        if not skill_ids and teaching_state:
            skill_ids = list(teaching_state.current_skill_ids)
        outcome = await self.learning_outcome.process_attempt(
            session,
            task=task,
            attempt=model,
            skill_ids=skill_ids,
            uptake=uptake,
        )
        due_retest_query_started = perf_counter()
        due_retests = await self.retests.list(
            session,
            user_id=request.user_id,
            status="due",
            offset=0,
            limit=100,
        )
        due_retest_query_ms = (perf_counter() - due_retest_query_started) * 1000
        pending_ids = [item.retest_plan_id for item in outcome.retest_plans]
        await SessionWorkingStateService(session).update_phase3(
            task,
            current_attempt_id=model.id,
            previous_attempt_id=model.revision_of_attempt_id,
            attempt_sequence=int(model.attempt_sequence or 0),
            feedback_uptake_status=(
                uptake.status.value if uptake is not None else None
            ),
            mastery_evidence_type=(
                outcome.evidence[0].evidence_type.value if outcome.evidence else None
            ),
            pending_retest_plan_ids=pending_ids,
        )
        message = self._uptake_message(uptake)
        return LearningActionResponse(
            interaction_id=interaction_id,
            action=request.action,
            status="completed",
            message=message,
            attempt=self.attempts.to_contract(model),
            feedback_uptake=uptake,
            mastery_evidence=outcome.evidence,
            mastery=outcome.mastery,
            retest_plans=outcome.retest_plans,
            teaching={
                "metrics": {
                    "attempt_sequence": model.attempt_sequence,
                    "attempt_revision_created": bool(model.revision_of_attempt_id),
                    "attempt_save_ms": attempt_save_ms,
                    "feedback_uptake_status": (
                        uptake.status.value if uptake else "not_applicable"
                    ),
                    "feedback_uptake_ms": uptake_ms,
                    "attempt_diff_ms": uptake_ms,
                    "due_retest_count": len(due_retests),
                    "due_retest_query_ms": due_retest_query_ms,
                    **outcome.metrics,
                }
            },
        )

    async def _complete_retest(
        self,
        session: AsyncSession,
        source_task: TaskModel,
        request: LearningActionRequest,
        interaction_id: str,
    ) -> LearningActionResponse:
        plan = await self.retests.complete(
            session,
            retest_plan_id=str(request.payload.get("retest_plan_id", "")),
            user_id=request.user_id,
            completed_task_id=str(request.payload.get("completed_task_id", "")),
            result=str(request.payload.get("result", "")),
        )
        completed_task = await session.get(TaskModel, plan.completed_task_id)
        assert completed_task is not None
        attempt = await LearningRecordRepository(session).latest_attempt(
            completed_task.id, request.user_id
        )
        if attempt is None:
            student_attempt = StudentAttempt(raw_text=request.student_answer)
            _, report, _ = self._phase3_context(completed_task, student_attempt)
            attempt = await self.attempts.create(
                session,
                task=completed_task,
                user_id=request.user_id,
                idempotency_key=f"{request.idempotency_key}:attempt",
                attempt=student_attempt,
                teaching_mode=TeachingMode.CHECK_MY_WORK,
                verification_report=report.model_dump(mode="json"),
            )
        outcome = await self.learning_outcome.process_attempt(
            session,
            task=completed_task,
            attempt=attempt,
            skill_ids=[plan.skill_id],
            retest_result=plan.result,
            retest_plan_source_task_id=plan.source_task_id,
        )
        await SessionWorkingStateService(session).update_phase3(
            completed_task,
            current_attempt_id=attempt.id,
            previous_attempt_id=attempt.revision_of_attempt_id,
            attempt_sequence=int(attempt.attempt_sequence or 0),
            feedback_uptake_status=None,
            mastery_evidence_type=(
                outcome.evidence[0].evidence_type.value if outcome.evidence else None
            ),
            pending_retest_plan_ids=[
                item.retest_plan_id for item in outcome.retest_plans
            ],
        )
        return LearningActionResponse(
            interaction_id=interaction_id,
            action=request.action,
            status="completed",
            message="复习结果已记录，并更新学习进度估计",
            attempt=self.attempts.to_contract(attempt),
            mastery=outcome.mastery,
            mastery_evidence=outcome.evidence,
            retest_plans=[
                self.retests.to_contract(plan),
                *outcome.retest_plans,
            ],
            teaching={"metrics": outcome.metrics},
        )

    def _phase3_context(
        self, task: TaskModel, attempt: StudentAttempt
    ) -> tuple[
        SolutionPacketV1 | None,
        VerificationReportV1,
        HintDecisionV1 | None,
    ]:
        structured = dict((task.result_content or {}).get("structured_result") or {})
        internal = structured.get(INTERNAL_TEACHING_KEY)
        raw_packet = (
            internal.get("full_solution_packet") if isinstance(internal, dict) else None
        )
        packet = (
            SolutionPacketV1.model_validate(raw_packet)
            if isinstance(raw_packet, dict)
            else None
        )
        if packet is None:
            report = VerificationReportV1(
                overall_status="manual_review",
                supported_scope=[],
                manual_review_required=True,
                warnings=["缺少可复用SolutionPacket，未进行自动正确性判断"],
            )
        else:
            report, _ = self.verifier.verify(attempt, packet)
        teaching_loop = structured.get("teaching_loop")
        raw_hint = (
            teaching_loop.get("hint") if isinstance(teaching_loop, dict) else None
        )
        try:
            hint = (
                HintDecisionV1.model_validate(raw_hint)
                if isinstance(raw_hint, dict)
                else None
            )
        except ValueError:
            hint = None
        return packet, report, hint

    @staticmethod
    def _uptake_message(uptake: FeedbackUptakeV1 | None) -> str:
        if uptake is None:
            return "已保存本次尝试"
        messages = {
            "applied_correctly": "你已经修正了目标步骤",
            "applied_incorrectly": "当前修改仍需检查",
            "partially_applied": "当前修改仍需检查",
            "not_applied": "未发现目标步骤发生变化",
            "indeterminate": "该过程较复杂，暂时无法自动判断",
            "not_applicable": "已保存本次尝试",
        }
        return messages[uptake.status.value]

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
