from __future__ import annotations

from hashlib import sha256

from app.contracts import HintDecisionV1, NextCheckQuestionV1, SolutionPacketV1


class NextCheckQuestionService:
    """Generates one bounded comprehension question without model calls."""

    def generate(
        self,
        *,
        task_id: str,
        packet: SolutionPacketV1,
        hint: HintDecisionV1,
    ) -> NextCheckQuestionV1:
        target_step = next(
            (
                item
                for item in packet.steps
                if item.step_id == hint.target_step_id
            ),
            packet.steps[0] if packet.steps else None,
        )
        if target_step is not None:
            question = f"下一步你会如何完成「{target_step.title}」？"
            answer_key = target_step.content[:1000]
            source = f"solution_step:{target_step.step_id}"
        elif hint.target_skill_ids:
            question = "你能用一句话说明这个知识点在本题中的作用吗？"
            answer_key = hint.hint_text
            source = f"skill:{hint.target_skill_ids[0]}"
        else:
            question = "你准备先检查哪个条件或关系？"
            answer_key = None
            source = "controlled_template"
        digest = sha256(
            f"{task_id}:{hint.hint_level}:{question}".encode()
        ).hexdigest()[:12]
        return NextCheckQuestionV1(
            question_id=f"check_{digest}",
            question_text=question,
            target_skill_ids=hint.target_skill_ids,
            target_solution_step_id=target_step.step_id if target_step else None,
            expected_response_type="short_text",
            source=source,
            answer_key_internal=answer_key,
        )
