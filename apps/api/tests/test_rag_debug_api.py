from __future__ import annotations


def test_rag_debug_page_and_status_do_not_expose_credentials(client) -> None:
    page = client.get("/debug/rag")
    status = client.get("/api/v1/debug/rag/status")

    assert page.status_code == 200
    assert "多模态 RAG 调试" in page.text
    assert status.status_code == 200
    body = status.text.casefold()
    assert "api_secret" not in body
    assert "authorization" not in body
    assert "flow_id" not in body
    assert status.json()["learn_flow_configured"] is False


def test_rag_debug_run_reuses_local_rag_and_stores_trace(client) -> None:
    response = client.post(
        "/api/v1/debug/rag/run",
        json={
            "question": "为什么电容电压不能突变？",
            "course_id": "CT",
            "intent": "explain_concept",
            "use_rag": True,
            "include_images": False,
            "use_reranker": False,
            "allow_cloud": False,
        },
    )

    assert response.status_code == 200, response.text
    trace = response.json()
    assert trace["trace_id"].startswith("debug_rag_")
    assert trace["route"]["original_agent_id"] == "LEARN_01_KNOWLEDGE_QA_V1"
    assert trace["final"]["provider"] == "local"
    assert trace["final"]["fallback_used"] is True
    saved = client.get(f"/api/v1/debug/rag/traces/{trace['trace_id']}")
    assert saved.status_code == 200
    assert saved.json()["request_id"] == trace["request_id"]


def test_rag_debug_compare_and_small_eval(client) -> None:
    comparison = client.post(
        "/api/v1/debug/rag/compare",
        json={
            "question": "锁存器和触发器有什么区别？",
            "course_id": "DE",
            "intent": "explain_concept",
            "comparison_mode": "rag_vs_no_rag",
        },
    )
    evaluation = client.post(
        "/api/v1/debug/rag/eval",
        json={"group": "CT", "allow_cloud": False, "limit": 1},
    )

    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["manual_review_required"] is True
    assert comparison.json()["a"]["final"]["provider"] == "local"
    assert comparison.json()["b"]["final"]["provider"] == "not_run"
    assert comparison.json()["b"]["retrieval"] == {}
    assert any(
        stage["name"] == "no_rag_no_cloud" for stage in comparison.json()["b"]["stages"]
    )
    assert evaluation.status_code == 200, evaluation.text
    assert evaluation.json()["total"] == 1
    assert evaluation.json()["misrouted_evaluated"] == 0
    assert evaluation.json()["misrouted_accuracy"] is None


def test_rag_debug_timeline_exposes_retrieval_phases(client) -> None:
    response = client.post(
        "/api/v1/debug/rag/run",
        json={
            "question": "为什么电容电压不能突变？",
            "course_id": "CT",
            "intent": "explain_concept",
            "allow_cloud": False,
        },
    )

    assert response.status_code == 200, response.text
    names = {stage["name"] for stage in response.json()["stages"]}
    assert {
        "query_normalization",
        "bm25_retrieval",
        "dense_retrieval",
        "image_retrieval",
        "rrf_fusion",
        "rerank",
    }.issubset(names)
