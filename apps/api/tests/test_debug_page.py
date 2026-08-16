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
    contracts = client.get("/debug-assets/ts/workspace-contracts.js")
    assert script.status_code == 200
    assert contracts.status_code == 200
    script_text = "\n".join((script.text, contracts.text))
    assert "research_analysis_v2" in script_text
    assert "researchAnalysisQuestionDetected" in script_text
    assert "effect size|confidence interval" in script_text
    assert "execute: tabularMaterials.length === 1" in script_text
    assert "researchAnalysisV2Summary" in script_text
    assert "renderBusinessView(structured.business_view" in script_text
    assert "structured.analysis_v2 === true" in script_text
    assert "research-analysis-estimand" in page.text
    assert "research-analysis-unit" in page.text
    assert "research-analysis-study-design" in page.text
    assert "research-analysis-evidence" in page.text
    assert "estimand:" in script_text
    assert "unit_of_analysis:" in script_text
    assert "study_design:" in script_text
    assert "request.evidence = evidence" in script_text
    assert "data_manifest" in script_text
    assert "researchTabularExtensions" in script_text
    assert "inferResearchAnalysisInputs" in script_text
    assert "用户分析说明：${question}" in script_text
    assert "request.variables = inferred.variables" in script_text
    assert "hiddenResearchFields = new Set(" in script_text
    assert '"analysis_steps"' in script_text
    assert '"reproducibility_requirements"' in script_text
    assert '"design_assessment"' in script_text
    assert '"effect_estimates"' in script_text
    assert '"limitations"' in script_text
    assert '"review_checklist"' in script_text
    assert "分析步骤" not in script_text
    assert "复现要求" not in script_text
