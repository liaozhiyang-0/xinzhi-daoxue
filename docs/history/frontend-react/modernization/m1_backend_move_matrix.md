# M1：Backend Architecture Inventory 与 Move Matrix

日期：2026-08-23

## 结论

当前后端已经有 `application/`、`capabilities/`、`runtime/`、`contracts/`、`bootstrap/` 等目标层，但 `services/` 仍同时承载 use-case coordination、专业能力、Runtime、infrastructure adapter、governance。M1 采用“先建 owner、后迁移 import”的方式，不做大规模目录搬运。

## Target owner map

| Target layer | Owner boundary | 首批目标 |
| --- | --- | --- |
| application | 请求编排、session/task commit、use-case adapter | `task_creation_service`、`task_control_service`、`task_session_commit`、`task_presentation` |
| capabilities/academic_solver | 题目规范化、策略、课程校验、求解结果 | `academic_solver_service`、`academic_review`、`ct_validator`、`ae_validator`、`de_validator` |
| capabilities/knowledge | RAG query、knowledge QA、asset governance | `knowledge_qa_service`、`knowledge_qa_runtime`、`knowledge_audit`、`course_asset_review` |
| capabilities/teaching | teaching foundation、attempt、hint、learning-facing response | `teaching_foundation`、`teaching_interaction`、`lesson_prep_runtime`、`assignment_review_runtime` |
| capabilities/research | research plan、evidence、analysis | `external_research_runtime`、`research_analysis_*`、`research_local_analysis` |
| capabilities/learning | attempts、mastery、retest、learning loop | `learning_loop`、`learning_outcome`、`learning_progress_runtime`、`retest_plans` |
| capabilities/general | general question、generic goal、fallback | `general_question_service`、`general_question_runtime`、`generic_goal_runtime` |
| runtime | lifecycle、execution、checkpoint、recovery、policies、events | `runtime_task_engine`、`task_runtime_*`、`runtime_*`、`event_service` |
| infrastructure | provider/RAG/storage/database/external adapter | `model_service`、`model_registry`、`rag_*`、`vector_store`、`storage`、`document_ingestion` |
| governance | verification、reflection、experience、evaluation | `agent_result_governance`、`high_risk_verification`、`reflection_*`、`experience_memory`、`evaluation_*` |
| compatibility | temporary old import path only | thin re-export modules after canonical owner exists |

## Move matrix

| current_path | responsibility | target_layer | target_path | importers/risk | compatibility | move_now |
| --- | --- | --- | --- | --- | --- | --- |
| `services/task_creation_service.py` | Task creation, route/plan/skill event orchestration | application/tasks | `application/tasks/coordinator.py` facade | API/bootstrap/evaluation; high | keep old service facade | yes, first |
| `services/task_control_service.py` | pause/resume/retry/cancel/input | application/tasks | `application/tasks/controls.py` | API/runtime; high | old path re-export | yes, first |
| `services/task_session_commit.py` | assistant/user message commit | application/tasks | `application/tasks/commit.py` | Task API/session; medium | old path re-export | yes |
| `services/task_presentation.py` | API-facing projection | application/tasks | `application/tasks/presentation.py` | API/history; high | old path re-export | yes |
| `services/academic_solver_service.py` | stable Academic Solver facade + professional execution | capabilities/academic_solver | `facade.py` then internal modules | many importers; very high | preserve `AcademicProblemSolverService` | partial |
| `services/internal_agent_execution.py` | internal worker dispatch plus embedded domain branches | application/capabilities | dispatch stays application; domain branches capability | very high; avoid second runtime | old path facade | partial |
| `services/learning_loop.py` | learning use cases and mastery updates | capabilities/learning | `loop.py` | API/feedback/task; high | old path facade | partial |
| `services/rag_retrieval.py` | retrieval policy and provider coordination | capabilities/knowledge + infrastructure/rag | `capabilities/knowledge/retrieval.py` + adapter | provider coupling; high | old path facade | partial |
| `services/research_local_analysis.py` | local analysis execution and I/O | capabilities/research + infrastructure | capability orchestrator + infrastructure IO | data path/security; high | freeze facade | no, audit first |
| `services/course_asset_review.py` | course asset governance | capabilities/knowledge | `asset_review.py` | admin/knowledge API; medium | old path facade | partial |
| `services/knowledge_audit.py` | knowledge readiness/governance | capabilities/knowledge | `governance.py` | admin/knowledge API; medium | old path facade | partial |
| `services/general_question_runtime.py` | general question capability, not runtime kernel | capabilities/general | `question_runtime.py` | generic route; medium | old path facade | partial |
| `services/skill_registry.py` | Skill owner | governance/capabilities boundary | existing `SkillRegistry` owner | Planner/Agent; critical | keep canonical existing owner | no move |
| `services/reflection_service.py` | bounded critic/revision | governance/reflection | existing reflection owner | result pipeline; critical | keep canonical existing owner | no move |
| `services/experience_memory.py` | Experience lifecycle | governance/experience | existing experience owner | memory/evaluation; critical | keep canonical existing owner | no move |
| `services/evaluation_*` | evaluation evidence and reports | governance/evaluation | existing evaluation owner | benchmark tooling; medium | keep until Phase M parity | no move |

## Risk rules

1. `AcademicProblemSolverService` remains the only public academic solver facade; no per-course public Solver is introduced.
2. `RuntimeTaskEngine` remains the only task execution engine.
3. Runtime modules may import contracts and capability interfaces, but not concrete KCL/KVL, RAG domain, teaching design, research synthesis, or learner diagnosis implementations.
4. Capability modules cannot depend upward on API routers.
5. Provider/RAG/database code moves behind infrastructure interfaces; no provider logic is copied into React.
6. A facade is removed only after `rg` proves zero importers and targeted tests pass.
