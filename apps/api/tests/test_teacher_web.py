from __future__ import annotations


def test_teacher_workspace_page_exposes_learning_metrics_controls(client) -> None:
    page = client.get("/teacher")

    assert page.status_code == 200
    assert "教师学习反馈工作台" in page.text
    assert "/debug-assets/teacher.css" in page.text
    assert "/debug-assets/teacher.js" in page.text
    assert 'id="teacher-metrics-filter"' in page.text
    assert 'id="teacher-feedback-distribution"' in page.text
    assert 'id="teacher-material-quality"' in page.text
    assert 'id="teacher-ocr-review"' in page.text
    assert 'id="teacher-ocr-action-filter"' in page.text
    assert 'id="teacher-ocr-priority-filter"' in page.text
    assert 'id="teacher-ocr-decision-filter"' in page.text
    assert 'id="teacher-ocr-reviewer"' in page.text
    assert 'id="teacher-error-review-queue"' in page.text
    assert 'id="teacher-error-review-summary"' in page.text
    assert 'id="teacher-course-readiness"' in page.text
    assert 'id="teacher-ocr-quality"' in page.text
    assert "PDF/OCR 复核队列" in page.text
    assert "Course Asset Readiness" not in page.text
    assert "Review action" not in page.text


def test_teacher_workspace_script_uses_aggregated_metrics_endpoint(client) -> None:
    script = client.get("/debug-assets/teacher.js")

    assert script.status_code == 200
    assert "/api/v1/learning/metrics" in script.text
    assert "feedback_uptake_determinate_rate" in script.text
    assert "/api/v1/knowledge/materials" in script.text
    assert "/api/v1/knowledge/ocr-review-queue" in script.text
    assert "/api/v1/knowledge/course-asset-review-queue" in script.text
    assert "/api/v1/knowledge/course-asset-readiness" in script.text
    assert "/api/v1/knowledge/ocr-quality-summary" in script.text
    assert "/api/v1/knowledge/ocr-review-decisions/" in script.text
    assert "teacher-ocr-review" in script.text
    assert "cache_status" in script.text
    assert "evidence_refs" in script.text
    assert "decision_note" in script.text
    assert "truncateOCRText" in script.text
    assert "filteredOCRRows" in script.text
    assert "saveOCRDecision" in script.text
    assert "teacher-ocr-filter-count" in script.text
    assert "没有符合当前筛选条件的候选项。" in script.text
    assert "/chunks" in script.text
    assert "/review" in script.text
    assert "material_review_status" in script.text
    assert "manual_review_required" in script.text
    assert "teacher-error-review-queue" in script.text
    assert "runtime_eligible" in script.text
    assert "deterministic_evidence_status" in script.text
    assert "deterministic_conflict_types" in script.text
    assert "deterministic_evidence_scope" in script.text
    assert "deterministic_validator_id" in script.text
    assert "验证器范围：" in script.text
    assert "验证器证据：" in script.text
    assert "review_evidence_quality" in script.text
    assert "证据引用：" in script.text
    assert "loadTeacherAssetReviewQueue" in script.text
    assert "loadCourseReadiness" in script.text
    assert "teacher-course-readiness" in script.text
    assert "证据待补" in script.text
    assert "evidence_checks" in script.text
    assert "teacher-readiness-evidence" in script.text
    assert "teacher_review_evidence" in script.text
    assert "教师证据质量：" in script.text
    assert "deterministic_evidence_ready_count" in script.text
    assert "验证器证据：" in script.text
    assert "deterministic_evidence_scope_counts" in script.text
    assert "knowledge_inventory" in script.text
    assert "teacher-readiness-knowledge" in script.text
    assert "ocr_decision_evidence" in script.text
    assert "teacher-readiness-ocr" in script.text
    assert "evaluation_provenance" in script.text
    assert "teacher-readiness-evaluation" in script.text
    assert "evaluationConsistency" in script.text
    assert "report_age_seconds" in script.text
    assert "teacher-ocr-quality" in script.text
    assert "decision_evidence" in script.text
    assert "student" not in script.text.lower()
