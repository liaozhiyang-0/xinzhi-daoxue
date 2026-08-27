# M1：Architecture Inventory 与 Move Matrix

## 目标
先分类，不先搬文件。

## 扫描
`services/`、`application/`、`runtime/`、`agents/`、`evaluation/`、`apps/web/`、`bootstrap/`。

## services 分类
APPLICATION / CAPABILITY_ACADEMIC / CAPABILITY_KNOWLEDGE / CAPABILITY_TEACHING / CAPABILITY_RESEARCH / CAPABILITY_LEARNING / CAPABILITY_GENERAL / RUNTIME / INFRASTRUCTURE / GOVERNANCE_VERIFICATION / GOVERNANCE_REFLECTION / GOVERNANCE_EXPERIENCE / GOVERNANCE_EVALUATION / COMPATIBILITY_FACADE / KEEP_IN_PLACE / REMOVE_LATER。

## Move Matrix 字段
current_path、responsibility、target_layer、target_path、importers、tests、risk、compatibility_strategy、move_now。

## 优先审计
- academic_solver_service.py
- internal_agent_execution.py
- learning_loop.py
- rag_retrieval.py
- research_local_analysis.py
- course_asset_review.py
- knowledge_audit.py
- general_question_runtime.py
- workspace.js

输出：
- `docs/history/frontend-react/modernization/m1_backend_move_matrix.md`
- `docs/history/frontend-react/modernization/m1_frontend_feature_inventory.md`

本阶段不 commit。
