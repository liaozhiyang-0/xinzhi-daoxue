from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilityBinding:
    capability_id: str
    handler_id: str
    aliases: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()


class CapabilityBindingRegistry:
    """Reviewed capability-to-handler bindings, separate from route ownership."""

    def __init__(self, bindings: tuple[CapabilityBinding, ...]) -> None:
        self._bindings = {item.capability_id: item for item in bindings}
        self._aliases = {
            alias: item.capability_id
            for item in bindings
            for alias in item.aliases
        }

    def canonicalize(self, capability_id: str) -> str:
        value = str(capability_id).strip()
        return self._aliases.get(value, value)

    def get(self, capability_id: str) -> CapabilityBinding:
        return self._bindings[self.canonicalize(capability_id)]

    def list(self) -> list[CapabilityBinding]:
        return [self._bindings[key] for key in sorted(self._bindings)]


def default_capability_binding_registry() -> CapabilityBindingRegistry:
    return CapabilityBindingRegistry(
        (
            CapabilityBinding(
                "teaching.lesson_design",
                "TEACH_01_LESSON_PREP_V1",
                aliases=("lesson_design",),
                skill_ids=("AE.COURSE_GOAL_ALIGNMENT", "AE.DIFFERENTIATED_PRACTICE"),
            ),
            CapabilityBinding(
                "teaching.assignment_review",
                "TEACH_02_ASSIGNMENT_REVIEW_V1",
                aliases=("answer_review",),
                skill_ids=("AE.FIRST_ERROR_DIAGNOSIS",),
            ),
            CapabilityBinding(
                "learning.first_error_diagnosis",
                "TEACH_02_ASSIGNMENT_REVIEW_V1",
                skill_ids=("AE.FIRST_ERROR_DIAGNOSIS",),
            ),
            CapabilityBinding(
                "learning.path_plan",
                "LEARN_01_LOCAL_RETRIEVAL_V1",
                aliases=("general_answer",),
                skill_ids=("AE.LEARNING_DEPENDENCY_ANALYSIS",),
            ),
            CapabilityBinding(
                "research.evidence_brief",
                "RESEARCH_01_ACADEMIC_SEARCH_V1",
                aliases=("academic_search", "evidence_review", "evidence_synthesis"),
                skill_ids=("RESEARCH.EVIDENCE_BRIEF",),
            ),
            CapabilityBinding(
                "knowledge.govern",
                "LEARN_01_KNOWLEDGE_QA_V1",
                aliases=("course_knowledge",),
                skill_ids=("KNOWLEDGE.ASSET_REVIEW",),
            ),
            CapabilityBinding(
                "academic.solve",
                "ACADEMIC_PROBLEM_SOLVER",
                aliases=("problem_solving",),
                skill_ids=("AE.ANALOG_FEEDBACK_ANALYSIS",),
            ),
            CapabilityBinding(
                "vision.circuit_parse",
                "ACADEMIC_PROBLEM_SOLVER",
                aliases=("deterministic_verification",),
                skill_ids=("AE.CIRCUIT_IMAGE_PARSE",),
            ),
            CapabilityBinding(
                "circuit.visualize",
                "tool.circuit.render",
            ),
        )
    )
