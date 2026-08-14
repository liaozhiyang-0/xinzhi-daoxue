def test_create_query_and_artifact(api, client) -> None:
    session = api.create_session()
    created = api.create_task(session["id"])
    assert created["status"] == "queued"
    assert created["provider"] == "local_agent"
    task = api.wait_for_task(created["id"])
    assert task["status"] == "completed"
    assert task["provider"] == "local_graph"
    assert len(task["artifact_ids"]) == 1

    artifact = client.get(f"/api/v1/artifacts/{task['artifact_ids'][0]}")
    assert artifact.status_code == 200
    assert artifact.json()["content"]["execution_source"] == (
        "academic_problem_solver_graph"
    )
    assert artifact.json()["content"]["academic_solution"]["course"] == "CT"

    history = client.get(f"/api/v1/sessions/{session['id']}/tasks")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [task["id"]]
    assert history.json()[0]["question"] == "求电阻两端电压"
    assert history.json()[0]["answer"]
    assert "result_content" not in history.json()[0]


def test_legacy_task_scenario_binds_catalog_agent_and_policy(api) -> None:
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        intent="lesson_prep",
        user_role="teacher",
    )
    payload.update(
        {
            "scene": "teaching",
            "scenario_id": "faculty_course_copilot_v1",
            "canonical_input": {"text": "璇峰府鎴戝噯澶囦竴鑺傝"},
        }
    )

    response = api.client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 202, response.text
    created = response.json()
    assert created["agent_id"] == "TEACH_01_LESSON_PREP_V1"
    assert created["route_status"] == "selected"
    assert created["input_content"]["scenario_id"] == "faculty_course_copilot_v1"
    assert (
        created["input_content"]["options"]["_scenario_catalog_bound"] is True
    )
    completed = api.wait_for_task(created["id"])
    assert completed["result_content"]["structured_result"]["scenario_id"] == (
        "faculty_course_copilot_v1"
    )


def test_task_creation_does_not_read_another_users_session(api) -> None:
    foreign_session = api.create_session(user_id="foreign-session-owner")
    response = api.client.post(
        "/api/v1/tasks",
        json=api.task_payload(foreign_session["id"]),
    )

    assert response.status_code == 404


def test_research_analysis_v2_api_persists_sanitized_provenance(api) -> None:
    session = api.create_session()
    options = {
        "research_analysis_v2": {
            "execute": False,
            "request": {
                "research_question": "Do the declared groups differ?",
                "hypothesis": "The declared groups differ.",
                "analysis_goal": "compare",
                "design": "experimental_comparison",
                "estimand": "treatment minus control mean outcome",
                "unit_of_analysis": "one row",
                "study_design": "randomized two-arm pilot; one measurement timepoint",
                "variables": [
                    {"name": "outcome", "role": "outcome", "unit": "score"},
                    {"name": "treatment", "role": "treatment", "unit": "label"},
                ],
                "data_manifest": {
                    "dataset_id": "api-provenance-test",
                    "version": "1",
                    "format": "csv",
                    "checksum_sha256": "0" * 64,
                    "row_count": 4,
                    "column_count": 2,
                    "authorized": True,
                    "source_ref": "local://api-provenance-test.csv",
                },
                "data_dictionary": "outcome is a score; treatment is a group",
                "evidence": [
                    {
                        "evidence_id": "method-api-contract",
                        "role": "method_reference",
                        "source_ref": "https://example.test/method-api-contract",
                        "cited": True,
                    }
                ],
                "exploratory": False,
            },
        }
    }

    response = api.client.post(
        "/api/v1/tasks",
        json=api.task_payload(
            session["id"], options=options, intent="data_analysis"
        ),
    )
    assert response.status_code == 409, response.text
    assert "数据分析功能当前已冻结" in response.text
    return


def test_research_analysis_v2_executes_uploaded_csv_attachment(api, client) -> None:
    session = api.create_session()
    upload = client.post(
        "/api/v1/files",
        data={"purpose": "unified_task_material"},
        files={
            "upload": (
                "experiment.csv",
                b"score,group\n68,control\n72,control\n78,treatment\n82,treatment\n",
                "text/csv",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    file = upload.json()
    attachment = {
        key: file[key]
        for key in (
            "id",
            "filename",
            "content_type",
            "size_bytes",
            "storage_key",
            "checksum_sha256",
        )
    }
    attachment["file_id"] = attachment.pop("id")
    options = {
        "research_analysis_v2": {
            "execute": True,
            "request": {
                "research_question": "处理组与对照组的 score 是否不同？",
                "hypothesis": "处理组的 score 高于对照组。",
                "analysis_goal": "estimate_effect",
                "design": "experimental_comparison",
                "estimand": "treatment minus control mean score",
                "unit_of_analysis": "one row per participant",
                "variables": [
                    {"name": "score", "role": "outcome", "unit": "score"},
                    {"name": "group", "role": "treatment"},
                ],
                "data_manifest": {
                    "dataset_id": file["id"],
                    "format": "csv",
                    "checksum_sha256": file["checksum_sha256"],
                    "authorized": True,
                    "source_ref": f"attachment:{file['id']}",
                },
                "data_dictionary": (
                    "score is the primary outcome; group is the randomized arm."
                ),
                "exploratory": False,
            },
        }
    }
    payload = api.task_payload(
        session["id"],
        options=options,
        attachments=[attachment],
        intent="data_analysis",
    )
    payload.update(
        {
            "scene": "dispatch",
            "scenario_id": "research_data_workbench_v1",
            "canonical_input": {
                "text": (
                    "这是一项随机双臂实验，每行代表一名受试者，score 是主要结局。"
                    "请比较 treatment 与 control 的差异并报告效应量。"
                )
            },
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 409, response.text
    assert "数据分析功能当前已冻结" in response.text


def test_research_analysis_v2_text_only_scenario_stays_local_plan(api) -> None:
    session = api.create_session()
    question = (
        "这是一项随机双臂实验，请比较 treatment 与 control 的 score 差异，"
        "并报告效应量、不确定性、诊断结果和结论边界。"
    )
    options = {
        "research_analysis_v2": {
            "execute": False,
            "request": {
                "research_question": question,
                "analysis_goal": "estimate_effect",
                "design": "experimental_comparison",
                "estimand": "treatment minus control mean score",
                "unit_of_analysis": "one row per participant",
                "exploratory": True,
            },
        }
    }
    payload = api.task_payload(
        session["id"], options=options, intent="data_analysis"
    )
    payload.update(
        {
            "scene": "dispatch",
            "scenario_id": "research_data_workbench_v1",
            "canonical_input": {"text": question},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 409, response.text
    assert "数据分析功能当前已冻结" in response.text
