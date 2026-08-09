def test_root_is_unified_home(client) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert "欢迎使用芯智导学" in response.text
    assert "/student" in response.text
    assert "/demo" in response.text


def test_debug_page_is_single_page_demo(client) -> None:
    response = client.get("/debug")
    assert response.status_code == 200
    assert "芯智导学" in response.text
    assert "演示中心" in response.text
    assert "presentation=1" in response.text
    assert "API Key" not in response.text

    script = client.get("/debug-assets/demo.js")
    assert script.status_code == 200
    assert 'api("/api/v1/scenarios"' in script.text
    assert 'api("/api/v1/scenarios/readiness"' in script.text
    assert "开始场景演示" in script.text
    assert "/api/v1/debug/execution/" in script.text


def test_workspace_exposes_research_analysis_v2_plan_gate(client) -> None:
    page = client.get("/workspace")
    assert page.status_code == 200
    assert "research-analysis-v2-panel" in page.text
    assert "先冻结研究设计" in page.text

    script = client.get("/debug-assets/workspace.js")
    assert script.status_code == 200
    assert "research_analysis_v2" in script.text
    assert "researchAnalysisQuestionDetected" in script.text
    assert "effect size|confidence interval" in script.text
    assert "execute: tabularMaterials.length === 1" in script.text
    assert "researchAnalysisV2Summary" in script.text
    assert "renderBusinessView(structured.business_view" in script.text
    assert "structured.analysis_v2 === true" in script.text
    assert "research-analysis-estimand" in page.text
    assert "research-analysis-unit" in page.text
    assert "research-analysis-study-design" in page.text
    assert "research-analysis-evidence" in page.text
    assert "estimand:" in script.text
    assert "unit_of_analysis:" in script.text
    assert "study_design:" in script.text
    assert "request.evidence = evidence" in script.text
    assert "data_manifest" in script.text
    assert "researchTabularExtensions" in script.text
    assert "inferResearchAnalysisInputs" in script.text
    assert "用户分析说明：${question}" in script.text
    assert "request.variables = inferred.variables" in script.text
    assert "hiddenResearchFields = new Set(" in script.text
    assert '"analysis_steps"' in script.text
    assert '"reproducibility_requirements"' in script.text
    assert '"design_assessment"' in script.text
    assert '"effect_estimates"' in script.text
    assert '"limitations"' in script.text
    assert '"review_checklist"' in script.text
    assert "分析步骤" not in script.text
    assert "复现要求" not in script.text
