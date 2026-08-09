from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.contracts.research_analysis import (
    ResearchAnalysisResult,
    ResearchReviewChecklist,
    ResearchReviewDecision,
    ResearchReviewItem,
    ResearchReviewSubmission,
)


class ResearchAnalysisReviewService:
    """Build a pending human-review checklist from deterministic outputs."""

    def build_checklist(
        self, result: ResearchAnalysisResult
    ) -> ResearchReviewChecklist:
        items = [
            ResearchReviewItem(
                review_id="data_authorization",
                category="data",
                question=(
                    "Is the dataset authorized, versioned, and matched to the "
                    "supplied checksum?"
                ),
            ),
            ResearchReviewItem(
                review_id="missingness_strategy",
                category="data",
                question=(
                    "Does the executed missing-data handling match the frozen "
                    "analysis plan?"
                ),
            ),
            ResearchReviewItem(
                review_id="design_estimand",
                category="design",
                question=(
                    "Do the research question, unit of analysis, design, and "
                    "estimand agree?"
                ),
            ),
            ResearchReviewItem(
                review_id="method_assumptions",
                category="method",
                question=(
                    "Were the method assumptions and diagnostics reviewed by a "
                    "qualified researcher?"
                ),
            ),
            ResearchReviewItem(
                review_id="robustness_findings",
                category="method",
                question=(
                    "Are the reported robustness and sensitivity findings "
                    "sufficient for the claim?"
                ),
            ),
            ResearchReviewItem(
                review_id="interpretation_boundary",
                category="interpretation",
                question=(
                    "Does the interpretation stay within the plan's causal, "
                    "sampling, and forecasting boundaries?"
                ),
            ),
            ResearchReviewItem(
                review_id="artifact_reproducibility",
                category="artifact",
                question=(
                    "Can each output artifact be reopened and verified by its "
                    "checksum?"
                ),
            ),
        ]
        if not result.evidence_ids:
            items.append(
                ResearchReviewItem(
                    review_id="method_evidence_gap",
                    category="method",
                    question=(
                        "Is the absence of a citable method reference acceptable "
                        "for this analysis?"
                    ),
                )
            )
        return ResearchReviewChecklist(items=items)

    def persist_submission(
        self,
        artifact_root: Path,
        task_id: str,
        submission: ResearchReviewSubmission,
    ) -> ResearchReviewDecision:
        """Persist a signed review in the task-scoped artifact directory."""

        checklist = ResearchReviewChecklist(
            items=submission.items,
            reviewer_id=submission.reviewer_id,
            signed_off=submission.signed_off,
        )
        if not checklist.ready_for_signoff or not checklist.signed_off:
            raise ValueError("签字前必须完成全部人工复核项")
        signed_at = datetime.now(UTC)
        unsigned = {
            "reviewer_id": submission.reviewer_id,
            "reviewer_role": submission.reviewer_role,
            "checklist": checklist.model_dump(mode="json"),
            "signed_at": signed_at.isoformat(),
        }
        decision_hash = hashlib.sha256(
            json.dumps(
                unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        decision = ResearchReviewDecision(
            reviewer_id=submission.reviewer_id,
            reviewer_role=submission.reviewer_role,
            checklist=checklist,
            signed_at=signed_at,
            decision_hash=decision_hash,
        )
        root = artifact_root.resolve()
        task_dir = (root / task_id).resolve()
        try:
            task_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError("review_task_id_outside_artifact_root") from exc
        task_dir.mkdir(parents=True, exist_ok=True)
        target = task_dir / "research_review_decision.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(decision.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        return decision

    @staticmethod
    def load_decision(
        artifact_root: Path, task_id: str
    ) -> ResearchReviewDecision | None:
        root = artifact_root.resolve()
        target = (root / task_id / "research_review_decision.json").resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("review_task_id_outside_artifact_root") from exc
        if not target.is_file():
            return None
        return ResearchReviewDecision.model_validate_json(
            target.read_text(encoding="utf-8")
        )
