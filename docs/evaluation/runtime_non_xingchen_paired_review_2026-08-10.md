# 非星辰 Agent Runtime 配对评测与发布审核

日期：2026-08-10  
环境：开发环境 `http://127.0.0.1:8000`  
评测方式：原应用 Task API 创建任务，轮询 Task/SSE 事件，读取 Runtime checkpoint、事件轨迹和结果 artifact。  
输入：合成、脱敏输入；不含学生隐私、真实密钥或原始星辰 YAML。原始输入只保存在本地忽略目录，报告只保留脱敏后的结构化证据。

## 1. 授权与范围

- Provider：沿用现有开发环境配置；本轮不调用星辰 Flow，不修改 Provider 或 Flow ID。
- Agent 范围：`TEACH_01_LESSON_PREP_V1`、`TEACH_02_ASSIGNMENT_REVIEW_V1`、`RESEARCH_02_ACADEMIC_WRITING_V1`。
- 允许操作：开发环境多次配对执行，使用现有环境变量；自动审批只用于验证 Runtime 的控制链，单任务最多 3 次批准/冲突尝试。
- 不在范围：`SOLVER_CT v1.0`、`RESEARCH_03` 源文件和测试、生产发布、人工最终发布决定。

## 2. 前后端全流程结果

| Agent | Legacy | Runtime | 事件/Checkpoint | 自动预审结论 |
|---|---|---|---|---|
| `TEACH_01_LESSON_PREP_V1` | 完成 | 完成 | Legacy 18/2；Runtime 27/14，3 个节点 | 结构与前后端链路通过；语义仍需人工复核 |
| `TEACH_02_ASSIGNMENT_REVIEW_V1` | 完成 | 完成 | Legacy 18/2；Runtime 27/13，3 个节点 | 结构与前后端链路通过；语义仍需人工复核 |
| `RESEARCH_02_ACADEMIC_WRITING_V1` | 完成 | 完成 | Legacy 21/2；Runtime 27/13，3 个节点 | 结构与前后端链路通过；语义仍需人工复核 |

说明：最新三组配对均为 2/2 完成，确认 Agent ID 匹配、事件序列严格递增，且结果 artifact 可被原应用结果视图读取。历史失败样本仍保留在私有目录中，用于证明 child retry、结构化 fallback 和质量审批修复过程。`waiting_approval` 不代表成功；它表示 Runtime 保留了可恢复状态并等待控制。

## 3. 私有证据位置

以下目录已被忽略，不应提交到公共仓库：

- Lesson Prep 最新配对：[report.json](C:\Users\86184\Desktop\xinzhi-daoxue\.local_outputs\runtime_authorized_dev_e2e_20260810_lesson_prep_pair_after_quality_gate_fix\report.json)
- Assignment Review 最新配对：[report.json](C:\Users\86184\Desktop\xinzhi-daoxue\.local_outputs\runtime_authorized_dev_e2e_20260810_assignment_review_pair_after_runtime_hardening\report.json)
- Academic Writing 最新配对：[report.json](C:\Users\86184\Desktop\xinzhi-daoxue\.local_outputs\runtime_authorized_dev_e2e_20260810_academic_writing_pair_after_runtime_hardening\report.json)
- 历史失败与修复证据仍保留在同一 `.local_outputs` 根目录下，不进入公共仓库。

前端原应用成功链路的浏览器证据见：[runtime_non_xingchen_application_e2e_2026-08-10.md](C:\Users\86184\Desktop\xinzhi-daoxue\docs\evaluation\runtime_non_xingchen_application_e2e_2026-08-10.md)。该证据覆盖输入、Task、SSE、Runtime、外部检索和结果视图，但不替代语义等价评审。

## 4. 自动预审记录

评审人标识：`Codex automated structural review`  
评审日期：2026-08-10  
评审类型：结构、生命周期、事件顺序、结果契约和前后端展示链路预审；不是独立人工语义评审。

### 4.1 通过项

- Task 创建保持非阻塞，Provider 调用未放入路由请求线程。
- Runtime 已产生可恢复的 plan、节点状态、checkpoint、控制事件和结果 artifact。
- 已完成样本的事件序列严格递增，Legacy/Runtime 的目标 Agent ID 匹配。
- 三个新增业务 Agent 均完成最新 Legacy/Runtime 全流程配对。
- `runtime_child_run.py` 的失败 child 不再无限复用：失败且没有结果的 child 会在有界重规划时创建新的 durable child；新增回归测试已通过。
- Runtime 子 Agent 可在显式授权下对结构化输出错误使用已配置 fallback；Legacy 默认“不自动切换 Provider”的行为保持不变。
- Lesson Prep 的业务质量门与自适应重规划已分离：质量门只请求一次人工审批，批准后复用结果完成验证。

### 4.2 未通过项与风险

- 最新三组配对各只有一个合成输入样本，不能代表长期稳定性或真实用户分布。
- 本轮 fallback 只验证了开发环境已配置的 Provider 链路；未验证星辰 Flow，也不应据此推断生产 Provider 行为。
- 自动审批仅用于开发链路验证，不能替代教师、研究负责人或发布责任人的语义判断。
- 本轮未证明 Legacy 与 Runtime 的语义等价性，也未证明可设为生产默认。

## 5. 发布决定模板

### 自动建议

建议：**继续开发环境灰度，暂不设为默认，暂不发布生产**。  
理由：三条 Runtime 路径的应用级结构链路已通过一轮配对，但样本量有限且尚未完成独立语义评审；当前证据不足以支持生产默认切换。

### 人工最终决定（必须由责任人填写）

- 决策责任人：`待填写`
- 决策日期：`待填写`
- 选择：`继续灰度 / 设为默认 / 回滚`
- 语义等价结论：`待人工评审`
- 可接受质量结论：`待人工评审`
- 风险接受说明：`待填写`
- 发布备注：`待填写`

## 6. 可复现命令

```powershell
.\.venv\Scripts\python.exe scripts\run_runtime_authorized_dev_e2e.py `
  --base-url http://127.0.0.1:8000/api/v1 `
  --output .local_outputs/runtime_authorized_dev_e2e_20260810_assignment_review_pair `
  --case assignment_review_runtime_handoff `
  --mode both --timeout-seconds 60 --auto-approve-dev
```

执行前确认 API 使用开发 Runtime 配置；不要在生产环境使用 `--auto-approve-dev`。测试结果退出码为 0 才表示该报告中的所有运行完成；非 0 仍应保留报告，用于分析 timeout 或失败原因。

## 7. 后续门槛

## 8. 2026-08-10 follow-up verification

- The Lesson Prep quality gate now treats an explicitly empty business section (for example, `formative_assessment: []`) as a reviewable human-approval state. Missing or malformed fields still use the bounded replan path.
- Added an API-level regression test proving that approval of this quality gate reuses the checkpointed result, creates no Runtime plan proposal, and keeps the Runtime at iteration 0.
- The single-instance launcher now serializes startup per port and reuses a service that binds the port while another launcher is waiting. The lock is released after readiness and does not terminate unknown listeners.
- Targeted checks passed: Lesson Prep unit tests (9 passed), Lesson Prep API regression (1 passed), Ruff, and Mypy.
- A fresh single-case Legacy/Runtime pair was run after a clean single-instance startup. Legacy completed; Runtime remained `waiting_approval` after two `lesson_prep_execution_failed` plan proposals caused by `StructuredOutputError` in the local provider path. This run does not validate the empty-section quality gate because verification was never reached; it remains a non-passing E2E artifact and must not be described as full Runtime success.
- A controlled Lesson Prep Runtime retry completed with 0 approvals, 12 checkpoints, and strictly increasing events; its structured result contained a non-empty `formative_assessment`, so it validates the normal completion path rather than the empty-section gate.
- Additional batched evidence: the four teaching runs completed 4/4, the remaining eight runs completed 7/8 (the only timeout was Solver Legacy), and the Lesson Prep Runtime retry completed. These are separate bounded runs, not one clean 14-run release qualification.
- The E2E runner now records redacted Runtime failure diagnostics (`failure_codes`, `failed_node_ids`, proposal count, and proposal reason codes). Re-reading the preserved Lesson Prep timeout classifies it as `StructuredOutputError` → `subagent_child_result_missing` → `dependency_failed`, with two `lesson_prep_execution_failed` proposals; this is distinct from the empty-section quality-gate path.
- After forwarding the Runtime structured-fallback option through the Spark reason-then-structure pipeline, a fresh single-case Lesson Prep Runtime run completed with one quality-gate approval, zero plan proposals, and `formative_assessment: []` preserved for human review. The observed `StructuredOutputError` was classified as recovered (`unresolved_failure_codes=[]`), not as a terminal Runtime failure.

1. 对三条路径各增加至少 3 个不同合成输入，检查连续完成率、fallback 率和审批恢复率。
2. 对三条路径各做独立语义评审，逐对记录等价性、质量和风险。
3. 只有在语义评审、前端显示检查和责任人发布决定均完成后，才考虑扩大灰度。
## 9. 2026-08-11 LearningLoop public API slice

This is a bounded, synthetic development verification and is not release
evidence. The LearningLoop Runtime is selected by the API process profile;
the public request remains `POST /api/v1/learning/actions`.

- Added `scripts/run_learning_runtime_authorized_dev_e2e.py`. It captures
  redacted action, Runtime status, approval controls, status transitions, and
  task event ordering. `--task-id` can isolate LearningLoop API/control tests
  from a slow Task creation/provider path.
- Runtime process profile: `TEACHING_INTERACTION_V1` and
  `LEARNING_PROGRESS_V1` were enabled. Teaching hint and learning-progress
  revision both completed with `runtime_run_id`, matching route assertions,
  and strictly increasing events.
- Legacy process profile: the same two public actions completed without a
  Runtime run, with matching Legacy route assertions and strictly increasing
  events. The two profiles were started serially; no concurrent API/Worker
  pair was used.
- A Runtime manual-review case observed the transition
  `waiting_approval -> completed` after one development approval control.
- Readiness remained fail-closed: both capabilities reported
  `canary_release_eligible=false` and
  `learning_runtime_authorized_paired_evidence_missing`.
- A fresh Task creation attempt exceeded the bounded 45-second observation
  window in the local Academic Solver provider node. It is recorded as a
  Task-path timeout and does not invalidate or replace the completed
  LearningLoop API-only slice.

Private artifacts are under `.local_outputs/learning_runtime_authorized_dev_e2e_20260811_*`.
They are ignored and must not be committed.

## 10. 2026-08-11 control and recovery follow-up

- Added a redacted `learning_runtime` projection to the execution debug API.
  It exposes the latest LearningLoop run identifier, status, state version,
  available controls, and node statuses without request snapshots or student
  answers. A regression test verifies the projection against a real test-app
  LearningLoop run.
- The student workspace now keeps LearningLoop controls separate from the
  generic Task Runtime controls and submits them through
  `/api/v1/learning/runtime/{run_id}/control` with the current state-version
  CAS and idempotency key.
- The empty business-section recovery regression passes: an approved
  `formative_assessment: []` checkpoint completes at iteration 0 with one
  provider result and no repeated proposal.
- Verification passed: 20 focused tests for Lesson Prep, workspace controls,
  UI contracts, and the debug projection; 9 LearningLoop control API tests;
  5 SSE/readiness/status tests; Ruff, Mypy, and Node syntax checks.
- A fresh HTTP attempt was not release evidence: the local API returned 502
  because PostgreSQL/Redis dependencies were not running. The in-app browser
  transport was also unavailable, so no visual browser acceptance is claimed.
  Full Task creation, SSE, approval, recovery, and result-display E2E remains
  pending a dependency-backed single-instance run.

## 11. 2026-08-11 plan-proposal control boundary follow-up

- The Runtime control projection now distinguishes a pending adaptive plan
  proposal from an ordinary Runtime quality or side-effect approval. While a
  plan proposal is pending, the task control API exposes a redacted proposal
  summary and fail-closed control reasons; the proposal must use the explicit
  `/tasks/{task_id}/runtime-plan-proposals/{proposal_id}/decision` endpoint.
- The authorized development E2E runner now detects the pending proposal and
  sends that explicit decision. The workspace exposes separate apply/reject
  controls for this state; ordinary quality approval continues to use the
  existing task approval endpoint.
- In a fresh synthetic Lesson Prep HTTP task (`task_6642a13ee6354a4b936f860a9262c05b`),
  the bounded runner timed out before the proposal became visible because the
  local provider path exceeded the observation window. A bounded continuation
  then applied exactly one pending proposal, observed the normal quality gate,
  approved that gate once, and completed the same task.
- The completed task ended at Runtime iteration 1, state version 24, with one
  proposal in `applied` status and 43 strictly ordered events ending in
  `task.completed`. No second plan proposal was created after the explicit
  decision. This is synthetic development evidence, not release qualification.
- The local provider `StructuredOutputError`/latency path remains a separate
  risk. Full paired evaluation and visual browser acceptance are still
  pending; no production or Xingchen conclusion is drawn from this case.

## 12. 2026-08-11 workspace SSE recovery follow-up

- The student/teacher workspace now keeps its `EventSource` alive after a
  transient error so the browser can reconnect using the existing
  `Last-Event-ID` cursor. This preserves the Task stream replay contract and
  avoids losing intermediate progress events.
- While the stream is recovering, the workspace continues a periodic status
  poll and refreshes the public Runtime control projection. This keeps pause,
  input, quality approval, and plan-proposal controls current even when the
  event channel is temporarily unavailable.
- Static workspace contract tests and Node syntax validation passed. Visual
  browser acceptance remains unverified because the browser transport was
  unavailable during this turn.

## 13. 2026-08-11 Assignment Review Runtime smoke evidence

- A fresh single-instance HTTP run used the public Task API for
  `assignment_review_runtime_handoff` with development-only approval enabled.
  The private report is under
  `.local_outputs/runtime_authorized_dev_e2e_20260811_assignment_runtime_followup/`.
- The run completed with `expected_agent_matched=true`, Runtime status
  `completed`, 13 checkpoints, 3 Runtime nodes, 27 strictly increasing Task
  events, zero Runtime failure codes, zero plan proposals, and one ordinary
  quality approval. The API process was stopped after the bounded run and port
  8000 was verified free.
- This is a current-path Runtime smoke result, not a paired Legacy/Runtime
  release artifact. The release preflight remains fail-closed because the
  required version-bound structural suite, semantic sidecar, and independent
  release decision are still absent for this Agent.

## 14. 2026-08-11 capability version binding follow-up

- Task Runtime capability descriptors now receive `agent_version` from the
  authoritative Agent Registry during application assembly. The descriptor
  factory remains provider-free and keeps its empty-version compatibility for
  isolated callers that do not supply a registry projection.
- This removes a version ambiguity from readiness/UI/release inspection: the
  Task capability identity is now bound to the registered Agent definition,
  while `version` continues to represent the Runtime plan version. No
  execution routing, Task/SSE contract, Provider call, or release permission
  was changed.
- Provider-free verification passed: capability descriptor, readiness API
  projection, Ruff, Mypy, and diff checks. Release preflight still requires
  independently captured authorized paired traces and semantic review; the
  new version field does not manufacture that evidence.

## 15. 2026-08-11 paired evidence packaging follow-up

- The offline paired-evidence packager now accepts both the original artifact
  layout (`artifacts/<agent>/<case>/<mode>/...`) and the current authorized
  E2E runner layout (`artifacts/<agent>/<case>/<sample>/<mode>/...`). Sample
  directories are included in the packaged case identity, preventing case
  collisions when one run contains multiple samples. A regression test covers
  the `sample-001` layout.
- A fresh isolated single-instance Assignment Review run used the explicit
  Runtime development launch profile and completed both Legacy and Runtime
  cases. The private report is under
  `.local_outputs/runtime_authorized_evidence_20260811_assignment_runtime_profile/`.
  The Runtime case had `agent_version=assignment-review-v1`,
  `runtime_plan_version=assignment-review-v1`, 12 top-level checkpoints, 3
  Runtime nodes, and one subagent lineage. Structural evaluation passed with
  one of one paired cases and no status, answer, provider, trace, latency, or
  model-call regression failures.
- The first direct-API attempt without the explicit Runtime launch profile was
  rejected from evidence because it produced a compatibility `run_kind=agent`
  trace without Runtime checkpoints. This confirms that the profile is part of
  the reproducible evidence precondition; it was not packaged as Runtime
  evidence.
- Release preflight was intentionally fail-closed: the structural suite was
  eligible, but `semantic_evidence_missing` blocked release. No semantic
  judgement or human release decision was fabricated. The generated files are
  development-only private artifacts and are not committed.

## 16. 2026-08-11 Lesson Prep paired diagnostic

- A fresh isolated single-instance Lesson Prep run completed both Legacy and
  Runtime cases under the explicit Runtime development profile. The private
  report is under
  `.local_outputs/runtime_authorized_evidence_20260811_lesson_runtime_profile_followup/`.
  Both cases matched `TEACH_01_LESSON_PREP_V1`, completed without timeout, and
  emitted strictly increasing Task events. The Runtime trace contained 14
  checkpoints, three Runtime nodes, one subagent retry after a recovered
  `StructuredOutputError`, and no unresolved Runtime failure.
- The run did not reproduce the earlier repeated-proposal loop: the Runtime
  report recorded zero plan proposals and no approval-budget exhaustion. The
  result nevertheless remains diagnostic, not release evidence. The Legacy
  side used the local fallback path with zero model calls, while Runtime used
  `local_agent` with two model calls; the offline packager therefore blocked
  the pair for provider and model-call regression. No structural suite or
  semantic release decision was promoted from this run.

## 17. 2026-08-11 General and Knowledge QA paired evidence

- Two additional bounded single-instance pairs completed under the explicit
  Runtime development profile: `GENERAL_QUESTION_V1` and
  `LEARN_01_LOCAL_RETRIEVAL_V1`. Each Legacy/Runtime pair completed 2/2 with
  zero Agent mismatches, zero timeouts, and strictly increasing Task events.
  Private artifacts are under
  `.local_outputs/runtime_authorized_evidence_20260811_general_knowledge_profile/`.
- The offline package produced one structural suite per Agent. Both suites
  passed structural evaluation with one of one paired cases, matching Agent
  and plan versions, valid Runtime traces, zero provider mismatch, zero
  status/answer/trace failures, and zero latency/model-call regression.
  General Question had 12 Runtime checkpoints; Knowledge QA had 9.
- Provider-free release preflight was run separately for both suites and
  returned exit code 1 with `semantic_evidence_missing`. The generated
  judgement templates remain incomplete and were not treated as semantic
  review; no canary/default decision was changed.

## 18. 2026-08-11 frontend execution and control smoke

- The execution debug page had two competing LearningLoop control
  implementations. The stale implementation disabled `pause`, `resume`, and
  `input`, while the later implementation was capability-driven. The stale
  block was removed, and generic Runtime dispatch now forwards all LearningLoop
  actions through the same backend projection, state-version CAS, request data,
  and idempotency-key boundary.
- A normal Task debug response includes an empty `learning_runtime` object.
  The frontend previously treated any non-null object as a LearningLoop run,
  causing dedicated LearningLoop status/control requests to return 404 and
  rendering the wrong control surface. The projection detector now requires a
  non-empty inline LearningLoop contract or an explicit LearningLoop marker.
- Focused verification passed: 11 UI/debug contract tests, Node syntax check,
  and diff check. A bounded single-instance Edge browser smoke also passed with
  zero page errors: workspace answer rendered, `xinzhi_last_task` persisted,
  execution console loaded, Runtime tab opened, and the normal Runtime control
  surface rendered without a LearningLoop misclassification. Private browser
  artifacts are under
  `.local_outputs/runtime_browser_acceptance_20260811_final/`.
- This browser smoke used the development mock provider and one temporary API
  instance; it is not a semantic release evaluation. The Lesson Prep approval
  recovery, all Runtime paired evaluations, and release preflight remain
  subject to the evidence and semantic-review gates recorded above.

## 19. 2026-08-11 Lesson Prep Runtime-only recheck

- A bounded single-instance Runtime-only recheck used the public Task API with
  the development mock profile and `--auto-approve-dev`. The first report is
  under `.local_outputs/runtime_authorized_evidence_20260811_lesson_runtime_final/`;
  the follow-up after the error-boundary fix is under
  `.local_outputs/runtime_authorized_evidence_20260811_lesson_runtime_budget_code/`.
- The run reached the first plan-proposal approval and resumed with strictly
  increasing events, but then failed closed after the resumed execution hit
  `ProviderNotConfiguredError` / `ProviderUnavailableError` in the local
  subagent path. The subsequent proposal candidate exceeded the remaining
  subagent budget; after the fix the task ended with the stable
  `runtime_replan_budget_exhausted` category, 21 checkpoints, and no second
  pending proposal event. This is a reproducible development diagnostic, not a
  passing E2E result.
- The result confirms the approval checkpoint itself is durable and applied,
  while the post-approval provider path still needs an explicitly configured
  provider profile before Lesson Prep can be called complete. No Runtime-wide
  or release conclusion is drawn from this failure.

## 20. 2026-08-11 Lesson Prep real-provider paired evidence

- A fresh single-instance paired run used the locally configured Spark/Qwen
  Providers with Xingchen disabled. The private report is under
  `.local_outputs/runtime_authorized_evidence_20260811_lesson_runtime_real_pair/`.
  Legacy and Runtime both completed 1/1 with matching
  `TEACH_01_LESSON_PREP_V1`, zero timeouts or event-order failures, and 2/2
  overall completed runs. The Runtime trace contained 26 checkpoints, three
  nodes, 47 strictly increasing events, one applied plan-proposal approval, and
  one quality-gate approval after a recovered `StructuredOutputError`.
- Offline packaging produced a version-bound structural suite with
  `structural_release_eligible=true`, `agent_version=lesson-prep-v1`, and
  `runtime_plan_version=lesson-prep-v1`. A redacted model preliminary sidecar
  was collected with `decision=needs_review`; the provider-free release
  preflight intentionally returned exit code 1 with
  `semantic_decision_not_pass`. No release, canary, or default decision was
  created.
- The development result is strong Runtime execution evidence, not production
  authorization. Independent semantic review must still assess the empty
  formative-assessment section and the Legacy/Runtime answer boundary before
  any migration decision.

## 21. 2026-08-11 Assignment Review real-provider paired evidence

- A fresh single-instance paired run used the locally configured Spark/Qwen
  Providers with Xingchen disabled. The private report is under
  `.local_outputs/runtime_authorized_evidence_20260811_assignment_runtime_real_pair/`.
  Legacy and Runtime both completed 1/1 with matching
  `TEACH_02_ASSIGNMENT_REVIEW_V1`, zero timeouts or event-order failures, and
  2/2 overall completed runs. The Runtime trace contained 13 checkpoints,
  three nodes, 27 strictly increasing events, and no unresolved failures.
- Offline packaging produced a version-bound structural suite with
  `structural_release_eligible=true`, `agent_version=assignment-review-v1`, and
  `runtime_plan_version=assignment-review-v1`. A redacted preliminary model
  sidecar was collected with `decision=needs_review`; the provider-free release
  preflight intentionally returned exit code 1 with
  `semantic_decision_not_pass`. No release, canary, or default decision was
  created.
- The Runtime output appropriately preserved the instruction not to auto-score,
  while adding process-oriented feedback that is not present in the Legacy
  excerpt. Independent semantic review must determine whether that difference
  is acceptable for the Assignment Review contract before any migration
  decision.

## 22. 2026-08-11 student frontend Runtime control hardening

- The student workspace now consumes the public
  `GET /tasks/{task_id}/runtime-controls` projection while a task is active.
  It exposes state-gated pause, resume, approval, plan-proposal decision, and
  bounded user-input controls without reading debug checkpoints or invoking a
  Provider from the browser.
- Student Task waiting states no longer leave the composer in an opaque
  indefinite wait: the page renders the Runtime checkpoint status, keeps the
  task wait alive until a terminal Task state, and reconciles controls after
  control submissions, `agent.progress`, and SSE reconnects. EventSource is
  kept open so the browser can send `Last-Event-ID`; a bounded poll reconciles
  public status while reconnecting. Session changes cancel the old wait and
  protect the new session from stale completion updates.
- Focused verification passed: 12 Runtime/SSE/non-blocking tests, Node syntax,
  Ruff, and diff checks. A browser-backed live student approval/recovery smoke
  was not executed because the configured in-app browser transport disconnected
  during setup; no browser result is claimed from this change.

## 23. 2026-08-11 student public Task API recovery evidence

- Added a provider-free public-boundary regression for a student Task: the task
  enters `waiting_input`, `GET /runtime-controls` exposes only the input action
  with the persisted state version, and `POST /input` resumes the same Runtime
  checkpoint to completion. The test also verifies that final controls are
  unavailable and stored event sequences remain unique and ordered.
- This is stronger evidence for the API/SSE contract consumed by the student
  page, but it is not a browser-rendering result. The live browser acceptance
  remains pending until the configured browser transport is available.

## 24. 2026-08-11 General Question real-provider paired evidence

- A bounded single-instance paired run used the locally configured Spark/Qwen
  Providers with Xingchen disabled. Legacy and Runtime both completed 1/1 with
  matching `GENERAL_QUESTION_V1`, zero timeouts or event-order failures, and
  2/2 overall completed runs. The Runtime trace contained 12 checkpoints,
  three nodes, 23 strictly increasing events, and no unresolved failures.
- Offline packaging produced a version-bound structural suite with
  `structural_release_eligible=true`, `agent_version=general-qa-v1`, and
  `runtime_plan_version=general-qa-v1`. A redacted preliminary model sidecar
  was collected with `decision=needs_review`; provider-free preflight returned
  `semantic_decision_not_pass`. No release, canary, or default decision was
  created.

## 25. 2026-08-11 Academic Writing real-provider diagnostic

- A bounded single-instance paired run used the locally configured Spark/Qwen
  environment with Xingchen disabled. Legacy and Runtime both completed 1/1
  with matching `RESEARCH_02_ACADEMIC_WRITING_V1`, zero timeouts or event-order
  failures, and 2/2 overall completed runs. Runtime contained 13 checkpoints,
  three nodes, and 27 strictly increasing events with no unresolved failure.
- Evidence packaging intentionally rejected this sample as structurally
  release-eligible. The Legacy result used the local fallback with
  `fallback_used=true` and zero model calls, while Runtime used `local_agent`
  with one model call. The packager reported
  `provider_mismatch_rate_above_threshold`,
  `model_call_regression_above_threshold`, and
  `single_pair_model_call_regression_above_threshold`; no semantic sidecar or
  release preflight was created. This is a useful migration diagnostic, not a
  passing release result.

## 26. 2026-08-11 Docker dependency readiness check

- `docker compose config --quiet` returned success, and the existing
  `xzd-postgres`, `xzd-redis`, `xzd-minio`, and `xzd-qdrant` containers were
  reported running/healthy by `docker compose ps --all` where health checks are
  defined.
- This was a read-only readiness check; no container restart, migration, API,
  or worker failure-recovery drill was performed. Production-equivalent
  restart evidence and a Runtime run against the Docker-backed dependencies
  remain outstanding.

## 27. 2026-08-11 Lesson Prep real-provider recovery recheck

- A fresh bounded single-instance paired run was executed after the Lesson
  Prep quality-gate and checkpoint-recovery changes. Legacy and Runtime both
  completed 1/1 with matching `TEACH_01_LESSON_PREP_V1`, zero timeouts, zero
  agent mismatches, and zero event-order failures.
- The Runtime result contained 13 checkpoints, three nodes, 27 strictly
  increasing events, no unresolved failure codes, and one explicit approval
  action. The post-approval path completed without a repeated proposal or
  `approval_budget_exhausted` terminal state. Both modes used `local_agent`
  without fallback in this run.
- Offline packaging produced a version-bound structural suite with
  `structural_release_eligible=true`, `agent_version=lesson-prep-v1`, and
  `runtime_plan_version=lesson-prep-v1`. Semantic review and a human release
  decision remain required; no release, canary, or default decision was
  created.

## 28. 2026-08-11 Docker-backed Runtime dependency smoke

- With the existing PostgreSQL, Redis, MinIO, and Qdrant containers running, a
  single API instance was started against the host-mapped dependencies. One
  `GENERAL_QUESTION_V1` Runtime task completed successfully with 12
  checkpoints, three nodes, 23 strictly increasing events, and no unresolved
  failure codes. The API process was stopped and target ports were free after
  the bounded run.
- The development machine's `.env` supplied DashScope credentials, so the
  smoke executed one real DashScope model call despite the mock provider
  request. No credential value was recorded or exposed. This is dependency
  chain diagnostics only—not provider-free evidence, a paired comparison, or
  release qualification—and the test harness was not reused for another run.

## 29. 2026-08-11 in-app browser transport retry

- A fresh attempt to connect the configured in-app browser for the student
  approval/recovery smoke failed during browser initialization with `Transport
  closed`. The temporary API was healthy on port 8021 and was stopped after
  the failed connection. No browser-rendering or visual approval result is
  claimed; the existing public API/SSE regression evidence remains separate.

## 30. 2026-08-11 Academic Writing structured-route convergence

- The `academic_writing` model route now uses `qwen_vision_primary` as its
  structured-output primary and `qwen_text_fast` as its fallback. The default
  ModelService policy remains fail-closed; this changes only the configured
  route order and does not enable unbounded fallback.
- A fresh bounded single-instance paired run completed both Legacy and Runtime
  for `RESEARCH_02_ACADEMIC_WRITING_V1`. Both results used `local_agent` with
  one model call, completed 2/2, and had zero timeouts, agent mismatches, event
  order failures, unresolved failures, or plan proposals. Legacy had two
  checkpoints and one node; Runtime had 13 checkpoints and three nodes.
- Offline packaging now reports `structural_release_eligible=true` with
  `agent_version=academic-writing-v1` and
  `runtime_plan_version=academic-writing-v1`. Independent semantic review and
  a human release decision are still required; no release, canary, or default
  authorization was created.
- A redacted preliminary model sidecar was generated with
  `decision=needs_review`; provider-free preflight returned exit code 1 with
  `semantic_decision_not_pass`. The sidecar is diagnostic evidence only and
  cannot substitute for an independent human semantic review.

## 31. 2026-08-11 Solver Runtime structural recheck

- A fresh bounded single-instance paired run exercised
  `ACADEMIC_PROBLEM_SOLVER` with Xingchen disabled. Legacy and Runtime both
  completed 1/1 with matching agent IDs, zero timeouts, zero agent mismatches,
  and zero event-order failures. Legacy produced two checkpoints and one
  node; Runtime produced 15 checkpoints and four nodes. Both traces had no
  unresolved failures or plan proposals.
- The paired sample used `local_graph` without fallback. The observed Legacy
  latency was 48.2 seconds and Runtime latency was 32.4 seconds; this is a
  single diagnostic sample and does not establish a stable performance
  baseline because earlier repeats showed substantial provider-latency
  variance.
- Offline packaging produced `structural_release_eligible=true` with
  `agent_version=solver-runtime-v1` and
  `runtime_plan_version=solver-runtime-v1`. No Solver source or frozen
  `SOLVER_CT v1.0` baseline was modified. Independent semantic review and a
  human release decision remain required; no release, canary, or default
  authorization was created.

## 32. 2026-08-11 browser-rendered workspace acceptance

- The repository browser acceptance completed against one isolated test API
  process with `APP_ENV=test`, `DEFAULT_AGENT_PROVIDER=mock`, Xingchen and
  external Providers disabled, and a temporary SQLite database. Its static
  and route preflight passed `19/19`; the browser flow produced 17 screenshots
  with zero page errors and no server left listening on the target port.
- The flow covered workspace empty state, CT/AE/DE task submission, evidence
  expansion and linking, process and answer-info tabs, Solver text and image
  input, Mock/fallback boundary presentation, execution and retrieval views,
  demo center, 1280x720 presentation mode, dark theme, and 390px mobile
  layout. The recorded assets are under
  `docs/reviews/workspace_v2_screenshots/`.
- This proves the static/browser interaction path under an isolated Mock
  configuration. It does not prove real Provider semantic quality, Runtime
  release authorization, or production browser behavior under external
  dependencies.

## 33. 2026-08-11 provider-free release matrix

- The latest authorized paired packages were checked independently with
  `scripts/check_runtime_release_preflight.py`, binding both expected Agent
  version and Runtime plan version. `GENERAL_QUESTION_V1`,
  `TEACH_01_LESSON_PREP_V1`, `TEACH_02_ASSIGNMENT_REVIEW_V1`,
  `RESEARCH_02_ACADEMIC_WRITING_V1`, and `ACADEMIC_PROBLEM_SOLVER` all report
  `structural_eligible=true`.
- All five checks intentionally returned exit code `1` with
  `semantic_eligible=false`, `release_eligible=false`, and the sole blocker
  `semantic_evidence_missing`. No Agent was promoted to canary or default,
  and no release authorization was created.
- This matrix is provider-free and proves the release gate remains fail-closed;
  it is not a semantic quality pass. The next valid step for each Agent is an
  independently reviewed, redacted sidecar bound to the same suite/case,
  followed by the separate human release decision required by the runbook.

## 34. 2026-08-11 version-bound release authorization gate

- Runtime launch policy now has an explicit optional release-authorization
  registry. When a configured Agent launch mode is `canary` or `default`, the
  registry requires a private JSON record bound to the structural suite,
  Agent version, Runtime plan version, launch mode, authorization reference,
  and approver reference. Missing, revoked, or mismatched records fail closed.
- The authorization registry is injected through
  `AGENT_RUNTIME_RELEASE_AUTHORIZATIONS=AGENT_ID=PATH`. If no launch mode is
  configured, existing explicit development opt-in behavior remains available;
  this is not production release authorization. The runbook and evidence
  intake contract now document the boundary.
- Ruff, Mypy, and the focused release-authorization/readiness/launch-policy
  tests passed (`33 passed`). A broader selected command was not accepted as a
  green release signal because it included an out-of-scope Research03-adjacent
  contract failure; no protected source or test was modified. No canary/default
  authorization record was created for the five current Agents.

## 35. 2026-08-11 role-aware Runtime controls and browser rerun

- The student Runtime controls now keep pause/resume/input available according
  to the public projection, but hide approval and plan-proposal apply/reject
  actions because the API requires a teacher or administrator. A waiting
  student sees an explicit checkpoint/approval status instead of a button that
  would predictably fail with HTTP 403. The unified workspace applies the same
  rule from the authenticated identity while preserving teacher/admin controls.
- Static contract tests passed for the student controls (`3 passed`) and the
  unified workspace controls (`7 passed`); both changed scripts passed Node
  syntax checks. The existing isolated Mock browser acceptance was rerun after
  the change: `19/19` preflight checks, 17 screenshots, zero page errors, and
  no listener left on port 8021.
- This is a UI authorization/state-presentation verification under the Mock
  profile. It does not establish real-provider semantic quality or a canary/
  default release decision; those gates remain unchanged.

## 36. 2026-08-11 fresh Lesson Prep single-instance follow-up

- A fresh bounded single-instance paired run used the local Spark/Qwen-backed
  profile with Xingchen disabled and completed both Legacy and Runtime for
  `TEACH_01_LESSON_PREP_V1`. The report is under
  `.local_outputs/runtime_authorized_dev_e2e_20260811_lesson_ui_followup/report.json`.
  Both runs completed 1/1 with matching Agent IDs, zero timeouts, zero Agent
  mismatches, and zero event-order failures; the Runtime trace had 26
  checkpoints and 47 strictly increasing events.
- The Runtime result preserved `formative_assessment: []` and reached the
  explicit `lesson_prep.quality_gate` approval. It also recovered two bounded
  `StructuredOutputError`/`subagent_child_result_missing` attempts through the
  configured replan path: the redacted report records two plan-proposal
  observations, one approved plan proposal, and one quality-gate approval, with
  no unresolved failure codes and no `approval_budget_exhausted` terminal state.
- This is useful recovery evidence, but not a clean zero-proposal qualification
  and not a semantic release pass. The structured-output instability remains a
  provider/profile risk to monitor; independent semantic review and the
  version-bound human release authorization are still required.

## 37. 2026-08-11 authenticated teacher browser diagnostic

- Added `scripts/run_runtime_teacher_browser_acceptance.js`, which starts one
  isolated API on port 8022, creates an administrator in a temporary SQLite
  database, logs in through `/login`, submits the Workspace Lesson Prep flow,
  and uses only the visible teacher approval control to resume the task. The
  command requires the existing isolated Playwright runtime:
  `NODE_PATH=.codex-tmp/playwright-runner/node_modules node scripts/run_runtime_teacher_browser_acceptance.js`
  (PowerShell uses `$env:NODE_PATH = (Join-Path (Get-Location) '.codex-tmp\playwright-runner\node_modules')`).
- The authenticated browser path was confirmed: the identity was `admin`, the
  approval button was visible and enabled, the task resumed after approval,
  page errors and request failures were empty, and the final task event
  sequences were strictly increasing. The bounded diagnostic then failed with
  `runtime_replan_budget_exhausted` after repeated internal structured-output
  failures; this is not evidence that approval persistence was lost.
- The development Lesson Prep Mock profile and its contract fixture were also
  aligned to the Runtime field `formative_assessment`. The dedicated Mock
  regression test verifies that the field is present even when it is an
  explicit empty list, while the Runtime unit tests cover approval without a
  replan. The browser diagnostic remains a failed semantic/provider stability
  check until the internal model profile produces a recoverable structured
  result within the bounded Runtime budget.

## 38. 2026-08-11 authenticated teacher browser recheck

- Re-ran the bounded browser diagnostic from a clean single-instance state;
  the redacted report is under
  `.local_outputs/runtime_teacher_browser_acceptance_42632/report.json`.
  The authenticated `admin` identity was accepted, the visible approval
  control was enabled, the task resumed after the first plan-proposal
  approval, and the browser observed 38 strictly increasing events with no
  page errors or request failures.
- The task still ended as
  `runtime_replan_budget_exhausted` (`proposed plan exceeds remaining Runtime
  budget`) after repeated internal structured-output failures. This repeats
  the Provider/profile instability, not an approval or checkpoint-loss
  finding; the frontend control path is verified, while real-provider Lesson
  Prep stability remains unresolved.
- The API regression now asserts that the successful post-approval path keeps
  exactly one persisted plan proposal in `applied` state and emits only
  `approval_required → applied` proposal events. The test does not convert the
  failed browser Provider run into a Runtime success claim.

## 39. 2026-08-11 Lesson Prep Runtime recovery follow-up

- The prior failure was reproduced with redacted Runtime budget evidence: the
  approval was applied, but unavailable internal model execution caused four
  failed typed child runs across the initial plan and one proposed replan. The
  terminal `runtime_replan_budget_exhausted` was therefore a Provider/profile
  availability failure, not an approval checkpoint loss.
- Runtime typed sub-agents now accept the existing definition-driven
  development Mock only when the internal Agent is unavailable and the Mock is
  allowed by the active development/test configuration. Configured Spark/Qwen
  execution remains the first path; Mock results retain the explicit `mock`
  provider and warning markers.
- A fresh authenticated browser acceptance run used one API PID and completed
  after the first approval: one child run, 27 strictly increasing events, no
  page errors, and no request failures. The result provider was `mock`.
- A separate real-provider paired run used one API PID, an isolated temporary
  SQLite database, Xingchen disabled, and the locally configured Spark/Qwen
  Providers. The private report is under
  `.local_outputs/runtime_authorized_evidence_20260811_lesson_runtime_real_pair_followup/`.
  Legacy and Runtime completed 2/2 with zero timeouts, agent mismatches, or
  event-order failures. Runtime used 13 checkpoints and three nodes, produced
  27 strictly increasing events, applied no plan proposal, and required one
  quality-gate approval. This is development verification evidence, not a
  production release authorization.

## 40. 2026-08-11 Assignment Review and Academic Writing real-provider pairs

- A single API process used an isolated temporary SQLite database, Xingchen
  disabled, and the locally configured Spark/Qwen Providers. The redacted
  report is under
  `.local_outputs/runtime_authorized_evidence_20260811_teaching_research_real_pairs/`.
- Assignment Review and Academic Writing each completed both Legacy and
  Runtime execution: 4/4 runs completed, with zero timeouts, Agent mismatches,
  or event-order failures.
- Both Runtime runs used three nodes, 13 checkpoints, and 27 strictly
  increasing events, required one quality approval, and applied zero plan
  proposals. All four runs reported `provider_used=local_agent`.
- This expands structural/application evidence only. Independent semantic
  review, version-bound authorization, release preflight, and a human canary
  decision remain required before any default migration.

Reproducible bounded command after starting exactly one API with the Runtime
development profile:

```powershell
.\.venv\Scripts\python.exe scripts\run_runtime_authorized_dev_e2e.py `
  --base-url http://127.0.0.1:8032/api/v1 `
  --case assignment_review_runtime_handoff `
  --case academic_writing_runtime_handoff `
  --mode both --pair-order alternate --timeout-seconds 240 `
  --auto-approve-dev `
  --output .local_outputs\runtime_authorized_evidence_20260811_teaching_research_real_pairs
```

## 41. 2026-08-11 General and local-knowledge real-provider pairs

- A separate single-instance run covered `GENERAL_QUESTION_V1` and
  `LEARN_01_LOCAL_RETRIEVAL_V1` with Xingchen disabled and the configured
  Spark/Qwen Providers. The redacted report is under
  `.local_outputs/runtime_authorized_evidence_20260811_general_knowledge_real_pairs/`.
- Both Legacy/Runtime pairs completed: 4/4 completed, zero timeouts, Agent
  mismatches, or event-order failures. General Runtime used three nodes, 12
  checkpoints, and 23 events; local-knowledge Runtime used two nodes, nine
  checkpoints, and 19 events. Neither required approval or a plan proposal.
- This confirms application-level Runtime ownership for the general and local
  retrieval paths under the bounded development profile. It does not establish
  semantic parity or production release authorization.

## 42. 2026-08-11 real-provider authenticated teacher browser flow

- `scripts/run_runtime_teacher_browser_acceptance.js` now supports the
  `XINZHI_TEACHER_BROWSER_PROVIDER_PROFILE=real_local` profile. Mock remains the
  default; the real profile disables Agent Mocks, enables the configured local
  Spark/Qwen Providers, and launches only `TEACH_01_LESSON_PREP_V1`.
- The bounded browser report is under
  `.local_outputs/runtime_teacher_browser_acceptance_real_local_20260811_retry/report.json`.
  One isolated API process authenticated as `admin`, created a Lesson Prep
  task, exposed an enabled approval button at the Runtime checkpoint, resumed
  the task after the visible approval action, and completed with
  `result_provider=local_agent`.
- The completed trace contained one Runtime child, three succeeded nodes, 27
  strictly increasing events, zero page errors, and zero request failures.
  This is real application/browser-flow evidence, but not semantic release
  evidence: independent semantic sidecars, version-bound human authorization,
  release preflight, and a canary decision remain outstanding.
- During the first real run, the API projection exposed `approve.available=true`
  while the UI retained a stale running projection. The unified Workspace now
  periodically reconciles public Runtime controls while SSE remains connected;
  the focused workspace contract suite passed 8/8 after the fix.

Reproducible bounded command (starts exactly one API/Worker process inside the
script):

```powershell
$env:NODE_PATH = (Join-Path (Get-Location) '.codex-tmp\playwright-runner\node_modules')
$env:XINZHI_TEACHER_BROWSER_PROVIDER_PROFILE = 'real_local'
node scripts\run_runtime_teacher_browser_acceptance.js
```

## 43. 2026-08-11 semantic release gate hardening

- Model-only semantic judgements remain accepted as diagnostic sidecars, which
  preserves the existing preliminary-review workflow.
- The actual release semantic gate now rejects `judge_type=model` even when
  `decision=pass`; only `human` or `hybrid` review with `decision=pass` can
  make `semantic_eligible=true`. The stable blocking reason is
  `semantic_judge_not_independent`.
- The change is covered by registry and provider-free preflight tests,
  including a model-only pass regression. It does not create a release record
  or promote any Agent; current canary/default decisions remain unchanged.

## 44. 2026-08-11 authenticated teacher browser Assignment Review flow

- The browser acceptance harness now accepts an explicit
  `XINZHI_TEACHER_BROWSER_SCENARIO` and verifies the selected capability's
  expected Agent ID. The Workspace capability buttons now bind their intent
  explicitly, so a prompt's subject matter cannot silently override the
  teacher's selected workflow.
- The bounded real-provider report is under
  `.local_outputs/runtime_teacher_browser_acceptance_real_assignment_review_20260811_final/report.json`.
  It used one API process, authenticated as `admin`, selected Assignment
  Review, and completed with `TEACH_02_ASSIGNMENT_REVIEW_V1` and
  `result_provider=local_agent`.
- The trace contained three succeeded Runtime nodes, one completed child run,
  27 strictly increasing events, one visible approval/recovery cycle, and no
  page errors or request failures. This is application/browser-flow evidence;
  it does not authorize semantic release, canary promotion, or default launch.

Reproducible bounded command (starts exactly one API/Worker process inside the
script):

```powershell
$env:NODE_PATH = (Join-Path (Get-Location) '.codex-tmp\playwright-runner\node_modules')
$env:XINZHI_TEACHER_BROWSER_PROVIDER_PROFILE = 'real_local'
$env:XINZHI_TEACHER_BROWSER_SCENARIO = 'assignment_review'
node scripts\run_runtime_teacher_browser_acceptance.js
```

## 45. 2026-08-11 LearningLoop development profile activation

- The explicit `--runtime-dev` launcher profile now enables both
  `TEACHING_INTERACTION_V1` and `LEARNING_PROGRESS_V1` in addition to the
  Task Teaching Runtime. The safe `.env.example` defaults remain disabled;
  this change affects only the named development/test profile.
- A bounded isolated SQLite API run used that profile contract with Mock
  Provider, Xingchen disabled, and one API process. The redacted report is
  under
  `.local_outputs/learning_runtime_dev_profile_20260811_recheck/report.json`.
- `teaching_request_more_hint` and
  `learning_progress_manual_review` both routed to Runtime and completed 2/2.
  Each entered `waiting_approval`, accepted one explicit approval, completed
  all four Runtime nodes, and preserved strictly increasing events (34 and 33
  events respectively). This proves development wiring and durable approval
  behavior; it is Mock/application evidence, not semantic or release evidence.

The bounded API action runner is:

```powershell
$env:AGENT_RUNTIME_TEACHING_INTERACTION_ENABLED = 'true'
$env:AGENT_RUNTIME_LEARNING_PROGRESS_ENABLED = 'true'
.\.venv\Scripts\python.exe scripts\run_learning_runtime_authorized_dev_e2e.py `
  --base-url http://127.0.0.1:8044/api/v1 `
  --mode runtime `
  --case teaching_request_more_hint `
  --case learning_progress_manual_review `
  --auto-approve-dev `
  --timeout-seconds 90 `
  --output .local_outputs\learning_runtime_dev_profile_20260811_recheck
```

## 46. 2026-08-11 LearningLoop authenticated browser approval recovery

- The Workspace browser harness now includes a bounded `learning_loop` scenario:
  it selects `check_my_work`, submits an anonymized circuit attempt, clicks the
  visible `request_more_hint` action, waits for the LearningLoop-specific
  controls projection, approves it, and verifies the updated teaching and
  learning panels.
- The first browser run exposed a real request-contract defect. The Workspace
  sent `decision` inside `data` for an `approve` action, while the LearningLoop
  control contract reserves `data` for `input`; the API returned HTTP 422 and
  the Runtime remained in `waiting_approval`. The Workspace now omits `data`
  for approval and keeps input data scoped to the `input` action.
- The post-fix report is under
  `.local_outputs/runtime_teacher_browser_acceptance_learning_loop_20260811_postfix_redacted/report.json`.
  One isolated authenticated API process completed the initial task and the
  LearningLoop Runtime. The learning run used `teaching_interaction`, four
  succeeded nodes, one accepted approval response, 39 strictly increasing
  task events, visible answer/teaching/progress panels, and zero page or
  request failures. The provider profile was `mock`; this is development
  application/browser evidence, not semantic parity or release authorization.

Reproducible bounded command (starts exactly one API process inside the script):

```powershell
$env:NODE_PATH = (Join-Path (Get-Location) '.codex-tmp\playwright-runner\node_modules')
$env:XINZHI_TEACHER_BROWSER_PROVIDER_PROFILE = 'mock'
$env:XINZHI_TEACHER_BROWSER_SCENARIO = 'learning_loop'
node scripts\run_runtime_teacher_browser_acceptance.js
```

## 47. 2026-08-11 execution debug LearningLoop control parity

- The execution debug page now uses the same LearningLoop control request
  contract as the Workspace: `data` is sent only for `input`; approval,
  pause, and resume send the action and current `state_version` without an
  empty data object.
- The focused UI contract suite is green at 18/18 after synchronizing stale
  assertions with the current capability-driven implementation.
- The authenticated browser harness also opens `/debug/execution` for the
  LearningLoop scenario and approves from the execution page itself. The
  bounded report is under
  `.local_outputs/runtime_teacher_browser_acceptance_learning_loop_execution_debug_20260811_post_timing/report.json`.
  It records one HTTP 200 accepted approval, a completed four-node
  `teaching_interaction` run, visible execution controls, 39 strictly
  increasing task events, and zero page/request failures. This remains Mock
  development evidence, not semantic or release authorization.

## 48. 2026-08-11 real-local LearningLoop browser path

- A bounded authenticated browser run used the `real_local` profile with one
  API process, an isolated SQLite database, Xingchen disabled, Agent Mocks
  disabled, and `ACADEMIC_PROBLEM_SOLVER=default`.
- The Workspace created the interactive `check_my_work` task, submitted
  `request_more_hint`, opened the Execution Debug page, and completed the
  LearningLoop Runtime. The redacted report is under
  `.local_outputs/runtime_teacher_browser_acceptance_learning_loop_real_local_20260811_retry/report.json`.
- The task routed to `ACADEMIC_PROBLEM_SOLVER` with
  `result_provider=local_graph`; the LearningLoop used four succeeded nodes,
  the approval node was explicitly `skipped` for this local path, the
  execution controls projection was visible, and 34 task events were strictly
  increasing. Page and request failures were both zero.
- This proves the real-local application/browser path and a no-approval
  terminal variant. It does not replace the Mock approval/recovery evidence,
  semantic review, or production release authorization.

## 49. 2026-08-11 student Workspace real-local LearningLoop path

- A bounded authenticated browser run registered a fresh student identity via
  `/login?mode=register&next=/student` and followed the real `/student` route,
  which serves the unified Workspace page. The run used one isolated API
  process, an isolated SQLite database, Xingchen disabled, and Agent Mocks
  disabled. The redacted report is under
  `.local_outputs/runtime_student_browser_acceptance_learning_loop_real_local_20260811_final3/report.json`.
- The authenticated identity was `student`. The Workspace created the
  interactive `check_my_work` task, submitted `request_more_hint`, and
  displayed the answer, teaching-loop, learning-progress, and student Runtime
  control surfaces. The task routed to `ACADEMIC_PROBLEM_SOLVER` with
  `result_provider=local_graph` and completed. The LearningLoop used four
  succeeded nodes, reached `completed`, and explicitly skipped the approval
  node because this real-local path does not require teacher approval.
- The run recorded 34 strictly increasing task events, with zero page errors
  and zero request failures. Student approval was not asserted in this path;
  the separate authenticated Mock teacher run remains the evidence for
  approval and recovery authorization.

## 50. 2026-08-11 RESEARCH_02 academic-writing browser path

- A bounded authenticated browser run exercised the visible Workspace
  academic-writing capability with one isolated API process, an isolated
  SQLite database, Xingchen disabled, Agent Mocks disabled, and the
  `RESEARCH_02_ACADEMIC_WRITING_V1=default` local Runtime profile. The redacted
  report is under
  `.local_outputs/runtime_research02_browser_acceptance_academic_writing_real_local_20260811/report.json`.
- The authenticated admin task completed through
  `RESEARCH_02_ACADEMIC_WRITING_V1` with `result_provider=local_agent`. The
  Runtime projection completed with `writing.observe`, `writing.execute`, and
  `writing.verify` succeeded; the execution node also produced a completed
  child run with a persisted state version.
- The browser observed 27 strictly increasing task events, zero page errors,
  and zero request failures. This is real-local application/browser evidence
  for RESEARCH_02 Runtime ownership and result delivery. It is not semantic
  approval of the rewritten text, external-provider equivalence, or production
  release authorization.

## 75. 2026-08-11 RESEARCH_03 readiness projection identity

- The API projection test now asserts that the RESEARCH_03 capability exposes
  `version=research-v2` and that `runtime_plan_available` follows the
  descriptor's explicit `enabled` state. The test environment keeps this
  candidate disabled by default, so readiness remains fail-closed while the
  capability identity is still observable and version-bound.
- The focused capability projection test passed `1 test`; Ruff also passed.

## 76. 2026-08-11 RESEARCH_03 paired-run harness registration

- Extended `scripts/run_runtime_authorized_dev_e2e.py` with the controlled
  `research_data_analysis_runtime_handoff` case and its explicit typed request
  payload. The case is configuration-driven and uses only synthetic,
  non-sensitive research metadata.
- The harness now treats the `research_analysis_v2` business option correctly:
  Runtime mode includes the explicit candidate request, while Legacy mode
  omits that option so the pair cannot accidentally execute the candidate
  Runtime. The harness regression suite passed `7 tests` and Ruff passed.
- This only makes future paired collection reproducible. No real RESEARCH_03
  pair was run in this step, and no release evidence or default launch was
  created.

## 77. 2026-08-11 explicit local profile enablement

- The `--runtime-dev` launcher profile now enables the RESEARCH_03 local
  Runtime service while deliberately leaving it out of the default launch-mode
  list. RESEARCH_03 therefore remains explicit opt-in in development and is
  not silently promoted by the profile.
- Launcher and paired-harness regression tests passed together (`23 tests`),
  with Ruff and sensitive-file checks passing.

## 51. 2026-08-11 researcher approval boundary and remaining quality risk

- Runtime approval is now role- and Agent-scoped: a `researcher` may approve
  only its own RESEARCH_01/RESEARCH_02 Runtime checkpoint, while teaching
  Runtime approval remains limited to teacher/admin identities. The backend
  task routes and Workspace control projection use the same allowlist. The
  focused role and UI contract tests passed; RESEARCH_03 was not included.
- The browser harness created a researcher account through the isolated admin
  UI, logged into a fresh context as `researcher`, and verified the identity
  and RESEARCH_02 routing. The bounded real-local report is under
  `.local_outputs/runtime_researcher_browser_acceptance_academic_writing_real_local_20260811_final6/report.json`.
- This run did not reach a successful researcher terminal result: the local
  academic-writing path entered two `runtime_plan_proposal` checkpoints,
  continued after the bounded approvals, and ended with
  `default Runtime execution did not complete (status=failed)` and
  `failure_category=not_configured`. It still recorded 45 strictly increasing
  events with zero page/request failures. This is an explicit semantic/provider
  quality risk, not evidence that researcher authorization works end to end.

## 52. 2026-08-11 researcher RESEARCH_01 academic-search path

- The Workspace now exposes an explicit `academic_search` capability card and
  registers the same capability in `/api/v1/capabilities`. Selecting it routes
  directly to `RESEARCH_01_ACADEMIC_SEARCH_V1`, avoiding intent auto-routing
  ambiguity in browser acceptance runs.
- A bounded real-local browser run created a researcher account through the
  isolated admin UI, logged in using a fresh browser context, created the
  academic-search task, and completed the Runtime. The redacted report is under
  `.local_outputs/runtime_researcher_browser_acceptance_academic_search_real_local_20260811/report.json`.
- The task completed with `result_provider=local_agent`; the Runtime control
  projection also completed. The run recorded 27 strictly increasing task
  events, with zero page errors and zero request failures. This verifies the
  researcher-facing application wiring and result delivery for RESEARCH_01;
  it is not a publication-quality assessment of retrieved evidence or release
  authorization.

## 53. 2026-08-11 Lesson Prep approval recovery recheck

- A bounded real-local browser run rechecked the Lesson Prep path after the
  empty-section quality-gate change, using one isolated API process, an
  isolated SQLite database, Xingchen disabled, and Agent Mocks disabled. The
  redacted report is under
  `.local_outputs/runtime_lesson_prep_browser_acceptance_real_local_20260811_retry/report.json`.
- The task routed to `TEACH_01_LESSON_PREP_V1`, reached exactly one
  `waiting_approval` quality checkpoint, and completed after approval with
  `result_provider=local_agent`. No `runtime_plan_proposal` was created; the
  Runtime finished at iteration `0`.
- The run recorded 27 strictly increasing task events, with zero page errors
  and zero request failures. This closes the previously observed empty-field
  approval/reproposal regression for this bounded real-local path. It does
  not prove all provider profiles or all Lesson Prep semantic cases are
  release-ready.

## 54. 2026-08-11 RESEARCH_02 researcher retry and stability boundary

- A subsequent bounded real-local run repeated the researcher-facing
  academic-writing path with one isolated API process and a fresh database.
  The redacted report is under
  `.local_outputs/runtime_researcher_browser_acceptance_academic_writing_real_local_20260811_retry7/report.json`.
- This retry completed through
  `RESEARCH_02_ACADEMIC_WRITING_V1` with `result_provider=local_agent`. It
  required one approved `runtime_plan_proposal`, then reached a completed
  Runtime with 40 strictly increasing events and zero page/request failures.
- An admin run under the same real-local provider profile also completed with
  `writing.observe`, `writing.execute`, and `writing.verify` all succeeded; its
  Debug projection is under
  `.local_outputs/runtime_admin_browser_acceptance_academic_writing_real_local_20260811_debug/report.json`.
- Together with the earlier researcher failure in section 51, these runs show
  intermittent Provider/structured-output stability risk rather than a
  deterministic researcher authorization or checkpoint-recovery failure. The
  path remains below semantic-quality and release-authorization sign-off until
  that stability risk is bounded with repeated evaluation evidence.

## 55. 2026-08-11 RESEARCH_02 repeated browser stability analysis

- The new diagnostic-only analyzer
  `scripts/analyze_runtime_browser_acceptance.py` excludes harness and identity
  failures, then aggregates redacted authenticated browser reports without
  starting a service or making a release decision. The focused analyzer tests
  passed.
- Thirteen valid researcher/RESEARCH_02 `real_local` samples were analyzed in
  `.local_outputs/runtime_researcher_academic_writing_stability_analysis_20260811.json`:
  8 completed, 5 failed, success rate `0.615385`. All 13 had strictly
  increasing events and zero page/request failures; the five failures ended
  with `default Runtime execution did not complete (status=failed)` after two
  plan proposals. Proposal counts were 0 for 4 samples, 1 for 2, and 2 for 7.
- This is reproducible stability evidence, not a semantic-quality or release
  decision. The current sample does not justify default release. Newly added
  `runtime_events` capture will make future failed samples distinguish Provider
  node errors from structured-output verification failures instead of relying
  on the generic terminal message.

## 56. 2026-08-11 RESEARCH_02 replan fallback preference

- The shared internal Agent execution boundary now applies the existing
  configured-route-fallback preference to `RESEARCH_02_ACADEMIC_WRITING_V1`.
  The first attempt keeps the configured primary route; after a bounded Runtime
  replan, the next attempt asks the model registry for its fallback alias rather
  than repeating the primary model. No Provider or credential is hardcoded.
- A focused regression test verifies the serialized `_prefer_route_fallback`
  option, while the existing Lesson Prep behavior remains covered. A bounded
  researcher real-local browser run after the change completed through one plan
  proposal, recorded 40 strictly increasing events, and had zero page/request
  failures. The redacted report is under
  `.local_outputs/runtime_researcher_browser_acceptance_academic_writing_real_local_20260811_fallback_fix1/report.json`.
- This is a resilience improvement, not proof that the 13-sample baseline
  stability risk has been eliminated. Repeated post-change samples and
  semantic-quality review are still required before release authorization.

## 57. 2026-08-11 RESEARCH_02 post-fix bounded recheck

- Six valid researcher/RESEARCH_02 `real_local` samples were collected after
  the replan fallback preference change and aggregated in the diagnostic-only
  report `.local_outputs/runtime_researcher_academic_writing_stability_postfix_20260811.json`.
  All 6 completed, for a post-change observed success rate of `1.0`; proposal
  counts were 0 for 1 sample and 1 for 5 samples.
- The six reports recorded 27 or 40 strictly increasing events, with zero
  page errors and zero request failures. The five replans exposed the
  expected `academic_writing_verification_requires_replan` approval reason;
  no failed node or Provider error was observed in this bounded sample.
- Compared with the earlier 13-sample baseline (8/13 completed), this is
  encouraging resilience evidence for the fallback change, but the sample is
  small and not a semantic-quality or release decision. More repeated runs,
  result-content review, and the full paired evaluation remain required.

## 59. 2026-08-11 RESEARCH_02 semantic release boundary

- Provider-free release preflight was run against the existing redacted
  RESEARCH_02 structural suite and its semantic sidecar, with explicit
  `agent_version=academic-writing-v1` and
  `runtime_plan_version=academic-writing-v1`. Structural eligibility passed,
  but semantic eligibility and release eligibility remained false with the
  blocking reason `semantic_judge_not_independent`.
- The review packet shows that the Runtime answer introduced concrete claims
  about teaching-method score improvement and student-satisfaction
  significance that were not present in the redacted input. The current
  sidecar correctly records this as preliminary model review with
  `decision=needs_review`; it is not an independent human approval.
- This is a semantic-quality finding, not a reason to weaken the structural
  contract or auto-promote the Agent. Human or hybrid review of the redacted
  paired output is still required before any canary/default decision.

## 60. 2026-08-11 student LearningLoop browser recheck

- A fresh bounded real-local browser run exercised the student account,
  problem-solving task, teaching interaction, and learning-progress UI on a
  new isolated port. The redacted report is under
  `.local_outputs/runtime_student_browser_acceptance_learning_loop_real_local_20260811_postfix1/report.json`.
- The task completed through `ACADEMIC_PROBLEM_SOLVER` with
  `result_provider=local_graph`, 34 strictly increasing events, and zero page
  or request failures. The LearningLoop Runtime completed at checkpoint
  `state_version=11`; `teaching.feedback.observe`, `apply`, and `verify` all
  succeeded while the approval node was skipped.
- The browser evidence confirms the answer, teaching loop, learning progress,
  and execution Runtime controls were visible. This verifies one student
  application path, but does not authorize the broader Runtime release or
  replace independent semantic review.
- The related student Web/API tests were executed in bounded groups with
  coverage disabled: 4 static/resource tests, 3 context/follow-up tests, and
  2 image/TaskRunner tests passed, in addition to the isolated-database test
  (10/10 selected tests passed). A single combined coverage invocation exceeded
  its 180-second limit, so the grouped results are the reproducible evidence;
  the combined command is not reported as passed.

## 61. 2026-08-11 teacher Assignment Review browser recheck

- A fresh bounded real-local browser run exercised the authenticated teacher
  workspace and Assignment Review capability on an isolated port. The
  redacted report is under
  `.local_outputs/runtime_teacher_browser_acceptance_assignment_review_real_local_20260811_postfix1/report.json`.
- The run authenticated as `admin`, routed to
  `TEACH_02_ASSIGNMENT_REVIEW_V1`, completed with `result_provider=local_agent`,
  and recorded 23 strictly increasing events with zero page/request failures.
- While the Runtime was running, the teacher control projection exposed pause
  as available and kept approval/input disabled; after terminal completion all
  controls were correctly disabled as `runtime_terminal`. This verifies the
  teacher Assignment Review path and control-state presentation, but not its
  independent semantic-quality or release authorization.

## 58. 2026-08-11 browser acceptance single-instance guard

- `scripts/run_runtime_teacher_browser_acceptance.js` now validates that its
  requested loopback port is free before spawning Uvicorn, and checks that the
  child process remains alive while waiting for health. This prevents a stale
  API from satisfying the health check and receiving a new acceptance run.
- A bounded conflict smoke test occupied port `8050`; the harness failed
  closed with an explicit `port ... is already in use` error and did not spawn
  an API. A normal mock Lesson Prep run on free port `8051` then completed with
  27 strictly increasing events and zero page/request failures; the port was
  released afterward.

## 62. 2026-08-11 student/admin course QA Runtime recheck

- The first student browser probe exposed a stale harness expectation:
  `course_qa` was expected to route to `GENERAL_QUESTION_V1`, while the
  workspace capability is explicitly local-knowledge enhanced and correctly
  routes to `LEARN_01_LOCAL_RETRIEVAL_V1`.
- After correcting the scenario expectation, the student run completed with
  19 strictly increasing events and zero page/request failures. The student
  account received HTTP 403 from the admin-only execution debug endpoint, so
  its `runtime_nodes` projection was empty; the event stream still contained
  successful `knowledge.execute` and `knowledge.verify` Runtime events.
- An independent bounded admin browser recheck completed on port `8058`.
  It recorded `knowledge.execute` and `knowledge.verify` as succeeded,
  `result_provider=iflytek_spark`, 19 strictly increasing events, and no page
  or request failures. The Provider label describes the local knowledge
  generation backend; the Runtime execution identity is established by the
  persisted run and node evidence.
- The acceptance harness now requires both knowledge Runtime node IDs for this
  scenario, so a future route that only matches the Agent ID but bypasses the
  Runtime will fail closed.

## 63. 2026-08-11 researcher Academic Search browser recheck

- A fresh bounded real-local browser run used the authenticated researcher
  workspace and routed to `RESEARCH_01_ACADEMIC_SEARCH_V1`. The redacted
  report is under
  `.local_outputs/runtime_researcher_browser_acceptance_academic_search_real_local_20260811_probe1/report.json`.
- The task completed with `result_provider=local_agent`; the event stream
  recorded successful `research.intent`, `research.fetch`, `research.answer`,
  and `research.verify` Runtime nodes. It contained 27 strictly increasing
  events and zero page/request failures.
- The researcher account received HTTP 403 from the admin-only execution
  debug endpoint, so the admin projection was unavailable in this report.
  The persisted task event stream still provides direct node-level Runtime
  evidence for the authenticated user path.
- The browser acceptance harness now requires all four Academic Search node
  IDs when this scenario is selected, preventing a route-only false positive.
- The same node-level assertion mechanism is now declared for the Lesson Prep,
  Assignment Review, Academic Writing, and student solver scenarios; optional
  replan nodes remain allowed while the stable base graph must be observed.

## 64. 2026-08-11 browser launcher and Workspace SSE recheck

- The three remaining browser launchers (`run_web_ui_browser_acceptance.js`,
  `auth_management_browser_acceptance.js`, and
  `multimodal_browser_acceptance.js`) now share a port/child-health guard with
  the Runtime acceptance harness. Each checks the requested loopback port
  before spawning Uvicorn and verifies that the spawned child is alive while
  waiting for `/api/v1/health`.
- A bounded conflict smoke occupied ports `8062`, `8063`, and `8064` in turn;
  all three launchers rejected the run with the explicit `already in use`
  error and did not attach to the occupied service.
- The existing student Workspace browser acceptance completed on isolated port
  `8065`: preflight passed `19/19`, 17 screenshots were produced across CT/AE/DE
  answers, evidence/context views, execution debug, dark theme, presentation,
  and 390px mobile layout. The run reported zero browser errors and the
  observed last answer render time was `4.0 ms`. The screenshots are retained
  under `.local_outputs/web_ui_browser_acceptance_20260811/`.
- SSE/Runtime UI regression tests passed as a focused group: 21 tests covering
  database sequence order, `Last-Event-ID` replay, terminal replay,
  concurrent appends, Runtime node order, plan-proposal events, Workspace
  controls, and the debug UI contract.
- This improves local product confidence for Task/SSE/UI boundaries, but does
  not replace the still-missing full paired Legacy/Runtime release suite or
  independent semantic approval.

## 65. 2026-08-11 non-RESEARCH_03 release preflight matrix

- A provider-free preflight sweep was run with explicit Agent and Runtime plan
  versions against the existing redacted structural suites. All seven
  non-RESEARCH_03 candidates had `structural_eligible=true`:
  `GENERAL_QUESTION_V1`, `LEARN_01_LOCAL_RETRIEVAL_V1`,
  `RESEARCH_01_ACADEMIC_SEARCH_V1`, `ACADEMIC_PROBLEM_SOLVER`,
  `TEACH_01_LESSON_PREP_V1`, `TEACH_02_ASSIGNMENT_REVIEW_V1`, and
  `RESEARCH_02_ACADEMIC_WRITING_V1`.
- None was release-eligible. General Question, Local Retrieval, Academic
  Search, Assignment Review, and Academic Writing were blocked by
  `semantic_judge_not_independent` because their sidecars were model-only.
  Solver and Lesson Prep were blocked by `semantic_sidecar_binding_invalid`
  for the supplied preliminary/template materials; these are not silently
  promoted to release evidence.
- This matrix separates Runtime execution/structural parity from semantic
  quality and independent authorization. RESEARCH_03 was intentionally not
  included in this sweep and remains the final migration/audit stage after the
  other core paths are closed.

## 66. 2026-08-11 semantic sidecar binding diagnostics

- The fail-closed Solver result was traced to an input-shape error, not a
  Runtime execution failure: the supplied
  `semantic_review_judgements_template/academic-problem-solver.json` is a
  case-keyed human-review template. It is not the array of
  `RuntimeSemanticEvidence` records produced by
  `scripts/collect_runtime_semantic_evidence.py`, and therefore cannot be
  passed to release preflight.
- The Lesson Prep preliminary sidecar is structurally well-shaped, but its
  `suite_id` is `lesson-real-pair-teach-01-lesson-prep-v1-b1488aaf84dc`, while
  the authorized structural suite expects
  `authorized-dev-e2e-teach-01-lesson-prep-v1-354f6d3eb9de`. The binding gate
  correctly rejects this cross-suite pairing.
- Runtime release loading now reports the case-keyed-template mistake
  explicitly and includes expected/actual suite IDs for suite mismatches. A
  regression test covers the template-shape rejection. No synthetic human
  approval was created and no release gate was weakened.
- The focused semantic evidence, canary release, preflight, and evidence-intake
  tests passed: `72 passed`. These tests are provider-free; they do not turn the
  existing model-only or mismatched local artifacts into independent semantic
  approval.

## 67. 2026-08-11 Runtime core contract regression sweep

- A bounded provider-free regression group covering Runtime contracts, control
  policy and CAS data, checkpoint control data, durable child runs, parallel
  recovery, observability, replay, subagents, plan proposals, release
  authorization, and launch policy passed `86 tests`.
- A separate collection-only attempt for
  `test_runtime_task_execution_path.py` exceeded the 30-second bound before
  collection completed and was stopped. It is not counted as a pass; the file
  also contains a protected research-analysis case and was not broadened in
  this sweep.

## 68. 2026-08-11 readiness evidence state separation

- The provider-free readiness projection now exposes additive
  `structural_release_eligible` and `semantic_release_eligible` fields for
  Task Agents and LearningLoop capabilities. The existing
  `canary_release_eligible` field remains the combined operational release
  result for compatibility.
- The Agent debug page consumes the explicit fields when present and keeps a
  conservative fallback for older payloads. It now displays structural,
  semantic, and Canary states separately, so a structurally valid but
  model-only semantic sidecar is not presented as a passed publication gate.
- Regression coverage passed `29 tests`, plus Ruff, Mypy, and Node syntax
  checks. The change is additive and provider-free; it does not alter launch
  policy or promote any capability.

## 69. 2026-08-11 readiness projection HTTP verification

- A single isolated test API on port `8066` was started with SQLite, all
  external Provider integrations disabled, and no Agent mocks used for the
  readiness requests. `GET /api/v1/agents/runtime-readiness` returned
  `provider_called=false` and exposed the three evidence fields on both the
  Agent projection and the top-level capability projection.
- `GET /api/v1/learning/runtime-readiness` exposed the same structural,
  semantic, and Canary fields for LearningLoop capabilities. The observed
  values remained false because no release evidence was configured.
- The local browser-control plugin disconnected during initialization, so no
  visual browser acceptance is claimed for `/debug/agents`. The isolated API
  process was stopped and port `8066` was released afterward.

## 70. 2026-08-11 cross-entry capability contract recheck

- The provider-free descriptor, cross-entry readiness, capability API, and
  LearningLoop readiness contracts passed `19 tests` after the evidence-state
  field expansion.
- The audit confirms that the non-RESEARCH_03 Task Runtime registry currently
  covers General Question, Local Retrieval, Academic Problem Solver, Lesson
  Prep, Assignment Review, Academic Writing, External Research, and the
  wildcard Goal Runtime. LearningLoop remains a separate request/result
  boundary and is exposed through its dedicated readiness projection.

## 71. 2026-08-11 reproducible readiness projection check

- Added `scripts/check_runtime_readiness_projection.py`, a provider-free,
  read-only check for the Task Agent and LearningLoop readiness endpoints. It
  verifies the three evidence-state booleans, checks that Task capability
  projections agree with their Agent projections, and confirms that no
  Provider execution signal is present.
- Added four focused unit tests covering the cross-entry contract, mismatched
  evidence state, Provider execution rejection, and the two-endpoint fetch
  path. The focused test file passed `4 tests` in `9.50s`; Ruff also passed.
- The check is not a release authorization mechanism and does not execute a
  task. It is intended as a repeatable preflight before later full-path
  validation.

## 72. 2026-08-11 RESEARCH_03 Runtime boundary hardening

- `ResearchAnalysisRuntimeService` now declares the stable
  `runtime_plan_version=research-v2`, so its capability descriptor and
  readiness/release evidence can bind to an explicit plan identity instead of
  falling back to `unversioned`/missing-plan behavior.
- Removed a duplicate RESEARCH_03 execution path in `TaskRunner`: the shared
  Runtime execution block owns the durable Run, and the compatibility branch
  now reuses its result or invokes the local internal executor only when the
  Runtime was not selected. This prevents a failed/canary handoff from
  replaying the same durable Run.
- The focused RESEARCH_03 boundary, descriptor, and contract matrix passed
  `30 tests`; the real TaskRunner plan-only regression passed `1 test` after
  aligning the fixture with the scenario's authorized teacher role. The
  readiness API/readiness service group passed `15 tests`; target Mypy, Ruff,
  `git diff --check`, and the sensitive-file scan passed.
- This hardens the migration seam and capability identity. It does not promote
  RESEARCH_03 to default or Canary: authorized paired evidence, independent
  semantic review, and human release approval remain absent.

## 73. 2026-08-11 RESEARCH_03 verification-contract refresh

- Updated the verification-contract tests to consume the current three-node
  `prepare -> execute -> verify` Runtime shape. The previous tests still
  unpacked the pre-prepare two-node helper result and failed before checking
  verification semantics.
- The complete bounded RESEARCH_03 contract group now passes `53 tests`, with
  Ruff passing for the updated test file. This is provider-free contract and
  local-analysis evidence; it is not paired release evidence.

## 74. 2026-08-11 RESEARCH_03 Task boundary smoke

- Added an explicit TaskRunner regression using a synthetic, non-sensitive
  typed analysis result. The request was accepted asynchronously, completed
  through `analysis.prepare`, `analysis.execute`, and `analysis.verify`, and
  returned through the existing Task/debug/event boundaries.
- The focused RESEARCH_03 Task path passed `2 tests` (plan-only fail-closed and
  execute/completed) with exactly one internal execution call and no legacy
  `model_generation` event. This proves application wiring and Runtime
  ownership only; it does not prove statistical semantic equivalence or
  release authorization.

## 78. 2026-08-11 RESEARCH_03 synthetic public-Task paired probe

- Added a bounded paired-harness case,
  `research_data_analysis_runtime_handoff`, using the same synthetic four-row,
  three-column CSV for Legacy and Runtime. The harness uploads only this
  non-sensitive fixture, binds a redaction-safe attachment reference and typed
  variable manifest, and keeps the business candidate opt-in to Runtime only.
- In one in-process `TestClient` application with isolated SQLite and external
  Providers disabled, both the Legacy and Runtime public Task paths completed
  and matched the expected `RESEARCH_03_DATA_ANALYSIS_V1` Agent. The Runtime
  produced `21` strictly ordered events, `3` Runtime nodes, and `12`
  checkpoints; the Legacy path produced `17` strictly ordered events. Runtime
  used `local_analysis_v2` with zero Provider calls; Legacy used a Provider
  explicitly marked `mock`.
- The offline paired analyzer found one usable sample and no input issues, but
  reported `requires_investigation=true` for single-sample latency overhead
  (Runtime lifecycle `531 ms` versus Legacy `170 ms`). This is diagnostic
  evidence only and must not be interpreted as a performance claim.
- The first probe failed closed because the synthetic request omitted the
  treatment variable role. Adding the declared `group` treatment and `outcome`
  variable roles allowed the quality gate to proceed; the gate was not
  weakened. No human approval, independent semantic sidecar review, real
  Provider result, or release authorization was performed.

## 79. 2026-08-11 authenticated frontend Runtime acceptance

- The in-app Browser connection was unavailable in this environment because
  both connection attempts returned `Transport closed`. The repository's
  bounded Edge/Playwright acceptance harness was therefore run with the
  bundled Node dependency, one isolated API process per case, isolated SQLite,
  Xingchen disabled, and the mock Provider explicitly labeled as `mock`.
- The authenticated administrator Lesson Prep path completed after one
  visible and enabled approval action. The report is under
  `.local_outputs/frontend_lesson_prep_acceptance_20260811/report.json` and
  records 27 strictly ordered events, the three lesson Runtime nodes and the
  `subagent.execute` child, with zero page errors and zero failed requests.
- The authenticated administrator LearningLoop path completed both the
  original solver task and the subsequent teaching interaction. The report is
  under `.local_outputs/frontend_admin_learning_loop_acceptance_20260811/report.json`.
  It records 39 strictly ordered events, four successful teaching Runtime
  nodes, an accepted execution-page approval, and visible answer, teaching-loop,
  learning-progress, and Runtime-control panels.
- The authenticated student LearningLoop path now treats a pending
  cross-role approval as an expected non-terminal UI state rather than trying
  to approve it as the student. The report is under
  `.local_outputs/frontend_student_learning_loop_acceptance_20260811_retry/report.json`:
  the student task completed, the learning action was accepted, the learning
  Runtime remained `waiting_approval`, the approval control stayed hidden, and
  the answer/teaching/progress panels were visible. The student's 403 response
  from the execution-debug endpoint is an expected authorization boundary;
  page errors and failed requests were both zero.
- These are authenticated application-wiring and UI-state records, not real
  Provider, semantic-equivalence, or release evidence. The harness change
  preserves the distinction between a completed task and a LearningLoop
  action awaiting an authorized reviewer.

## 80. 2026-08-11 release evidence configuration determinism

- Audited the version-bound release evidence loaders and found that repeated
  `AGENT_ID=PATH` entries in structural or semantic evidence configuration
  silently overwrote earlier entries. That made a release record dependent on
  configuration order and could hide a stale or conflicting artifact.
- `RuntimeCanaryReleaseRegistry.from_paths()` now rejects duplicate structural
  Agent entries and duplicate semantic sidecar Agent entries, matching the
  existing duplicate rejection behavior of the release-authorization registry.
- The bounded canary, semantic evidence, evidence-intake, and release
  preflight group passed `65 tests`; Ruff, target Mypy, and the sensitive-file
  scan passed. The local `.env` has no canary artifact, semantic sidecar, or
  release authorization configured, so no Agent is promoted by this change.

## 81. 2026-08-11 explicit human release authorization gate

- `RuntimeLaunchPolicy` previously returned no blocker when the structural
  and semantic evidence passed but the caller omitted the release-authorization
  registry. That allowed a directly constructed policy to enter canary/default
  without the required version-bound human approval.
- The policy now returns `release_authorization_missing` whenever the release
  gate is required and no authorization registry is supplied. Matching
  readiness fixtures now include an explicit authorization bound to Agent,
  suite, Agent version, Runtime plan version, and launch mode; missing or
  mismatched authorization remains Legacy/fail-closed.
- Launch-policy, authorization, and readiness regression tests passed `35`
  tests; Ruff and Mypy passed. This closes the policy-level omission but does
  not create a real approval record or promote any current Agent.

## 82. 2026-08-11 RESEARCH_03 handoff contract fixture refresh

- The bounded cross-entry regression found one stale RESEARCH_03 handoff
  fixture using the default `student` role even though the scenario contract
  authorizes only `teacher` and `researcher`. It was rejected with `422` before
  reaching the intended assertion about a failed Default Runtime not being
  masked by Legacy completion.
- The fixture now explicitly uses the authorized `teacher` role; no scenario
  allowlist or production authorization was broadened. The cross-entry,
  TaskRunner handoff, and release-preflight group passed `20 tests`, and Ruff
  passed. The corrected test confirms failed Default Runtime does not invoke
  Legacy Provider generation or emit a successful completion event.

## 83. 2026-08-11 readiness and launch authorization alignment

- Readiness inspection and the LearningLoop API projection now receive the
  same version-bound release-authorization registry used by the launch
  policy. Structural and semantic evidence remain reported independently, but
  `canary_release_eligible` is false when the matching human authorization is
  missing, revoked, or bound to a different Agent, suite, version, plan, or
  launch mode.
- Added a regression proving that missing authorization does not hide a
  semantic evidence pass: the result exposes `semantic_release_eligible=true`
  while remaining blocked with `release_authorization_missing`.
- The bounded readiness, cross-entry, API projection, and LearningLoop
  readiness group passed `30` tests. This change aligns diagnostics with the
  launch gate; it does not create a real approval record or promote any
  current Agent.

## 84. 2026-08-11 release-gated Task API recovery fixture alignment

- The recovery/plan-proposal integration sweep exposed one stale test fixture
  that manually enabled `release_gate_required=true` without supplying the
  matching version-bound authorization registry. The Runtime correctly stayed
  fail-closed, so the test never reached its intended Lesson Prep quality gate.
- The fixture now binds the same Agent, suite, version, Runtime plan, and
  `default` launch mode as the structural/semantic release fixture. No
  production authorization policy was weakened.
- The bounded shutdown-recovery, plan-proposal, checkpoint-control, parallel
  recovery, and replay group passed `23` tests. The Lesson Prep empty-section
  regression now proves one human quality approval resumes the same Runtime
  without entering the adaptive plan-proposal gate.

## 85. 2026-08-11 external research node-order contract refresh

- The core Runtime contract sweep found one stale Task API assertion for
  `RESEARCH_01_ACADEMIC_SEARCH_V1`. The declared plan and durable execution
  order are `research.intent -> research.fetch -> research.answer ->
  research.verify`; the assertion still expected the old answer-first order.
- The test now follows the declared dependency order. The corrected case
  passed independently; the surrounding 56-test core contract/Task/SSE sweep
  had `55` passing cases before this assertion refresh. The test's intentionally
  unconfigured DashScope path remained fail-closed and was not changed.

## 86. 2026-08-11 Redis queue and independent Worker boundary

- The API `TaskExecutor` boundary is now asynchronous and supports an explicit
  `local` or `redis` mode. In Redis mode, task creation, retry, resume,
  approval, Runtime input/reconciliation, and orchestration entry points only
  publish task IDs; they do not call `TaskRunner` or a Provider in the API
  process.
- `apps/worker/worker.py` owns the shared `TaskRunner` in a separate process.
  Redis has an at-least-once task-id transport, a renewable single-worker
  lease, and a periodic database recovery scan. Database task leases remain
  authoritative when a worker exits after consuming a message.
- The bounded unit/transport group passed `4` tests; the existing task
  executor reliability file passed `7` tests; Ruff and Mypy passed for the
  queue, executor, Worker, API dispatch changes, and entrypoint. A live Redis
  smoke verified publish/consume and worker-lease exclusion.
- A real local cross-process smoke used exactly one API and one Worker with a
  synthetic `GENERAL_QUESTION_V1` task. The API returned `202 queued`, the
  separate Worker completed the task, and the final event count was `23`.
  Evidence is recorded in
  `.local_outputs/runtime_worker_cross_process_20260811/report.json`.
  The temporary API port and Python processes were verified stopped afterward.
- This proves the development queue/Worker boundary and recovery ownership;
  it is not a production release claim. Docker queue-profile execution,
  crash/restart fault injection, SSE reconnect across process restart, and
  full paired Runtime evaluation remain outstanding.

## 87. 2026-08-11 Worker crash/restart and SSE restart recovery evidence

- Added a Worker fault-injection regression: the first Worker consumes a task
  and raises a simulated process-crash exception; a second Worker must use
  the recovery callback after the queue message is gone. The Worker test file
  now has `3` passing tests covering dispatch, single-owner rejection, and
  crash-to-recovery handoff.
- A real local process smoke used one API and two sequential Worker instances.
  Worker 1 claimed the task and was stopped after `RUNNING`; after the
  configured 30-second database lease expired, Worker 2 recovered and
  completed the same task with `23` ordered events. Evidence is recorded in
  `.local_outputs/runtime_worker_crash_recovery_20260811/report.json`, and
  cleanup verified no temporary API/Worker process or port remained.
- Added a cross-lifespan SSE regression proving that a terminal event stream
  reconnects from `Last-Event-ID=1` after the first API lifespan exits and a
  second API lifespan starts; the durable event sequence returns only event
  `2`.
- These checks establish local crash/recovery and durable SSE replay, but do
  not replace production Docker crash testing, frontend browser reconnection,
  or the remaining paired semantic/release gates.

## 88. 2026-08-11 frontend contract and deployment verification boundary

- The bounded static frontend/API contract group passed `19` tests, covering
  student Runtime controls, debug execution reconnect wiring, workspace
  controls, OpenAPI exposure, and the `Last-Event-ID` API contract. These are
  source/HTTP contract checks, not browser visual acceptance.
- `docker compose config --quiet` passed. A bounded
  `docker compose --profile queue-worker build queue-worker` attempt did not
  complete within `180` seconds, so no Docker image-build or container-runtime
  success is claimed; no queue-worker container was started.
- The in-app browser control transport returned `Transport closed` during
  setup. Browser interaction and screenshot evidence therefore remain
  unverified in this run; no browser result is inferred from the static tests.
- During a local launcher check, the environment exposed two same-command
  launcher/Uvicorn process chains on port `8000`; the exact project process
  tree was stopped before any UI work continued. The repository's launcher
  lock tests still pass, but this observed duplicate-start behavior requires
  a separate launcher-process audit before claiming single-instance startup
  in every shell invocation.

## 89. 2026-08-11 Docker build-context reduction and remaining build timeout

- The initial queue-worker image attempt exposed a roughly `3.1 GB` Docker
  build context caused by `.venv`, `.git`, pytest temporary directories,
  caches, local indexes, and ignored evaluation outputs. `.dockerignore` now
  excludes those development artifacts while retaining paths consumed by the
  API/Worker Dockerfile.
- After that change, a single follow-up build was allowed to run for `300`
  seconds. It still produced no queue-worker image, so the remaining delay is
  in dependency installation or later image layers rather than the original
  context transfer alone. The CLI was stopped after the bound; no container
  was started and the four existing infrastructure containers remained up.
- The next deployment task is to profile the Docker build or introduce a
  reproducible dependency/image cache strategy before claiming queue-worker
  container readiness.

## 90. 2026-08-11 Docker dependency-layer and CPU-wheel hardening

- `apps/api/Dockerfile` now derives the runtime dependency list directly from
  `apps/api/pyproject.toml`, installs dependencies before application source,
  and uses a BuildKit pip-cache mount. Source edits therefore do not invalidate
  the dependency layer, and no second hand-maintained requirements file was
  introduced.
- The default Docker build installs the CPU Torch wheel from the official CPU
  index before resolving the remaining requirements. This avoids pulling the
  CUDA 13 runtime into the default CPU-only API/Worker image; a deliberately
  GPU-enabled build can override `TORCH_INDEX_URL`.
- The bounded build confirmed a `29.37 kB` build context and selected
  `torch-2.13.0+cpu`; it reached the single `191.8 MB` CPU wheel download but
  did not finish within the observation window because the download stalled.
  No queue-worker image or container success is claimed. Compose parsing and
  `git diff --check` passed, and the exact build client tree was stopped.

## 91. 2026-08-11 authenticated Lesson Prep browser acceptance rerun

- The first harness attempt failed before application startup because the
  system Node process did not have the provided `playwright` module on its
  module path. The rerun used the workspace-bundled Node/Playwright runtime;
  it did not install an undeclared dependency.
- One isolated administrator `lesson_prep` case used SQLite, a mock Provider,
  and port `8052`. The authenticated Task completed as
  `TEACH_01_LESSON_PREP_V1`, observed `lesson.observe`, `lesson.execute`,
  `subagent.execute`, and `lesson.verify`, and emitted `27` strictly ordered
  events.
- The report records zero page errors and zero failed HTTP requests. The
  temporary API process and port were released after the run. This is real
  frontend application-wiring and UI-state evidence with an explicitly mock
  Provider; it is not real Provider, semantic-equivalence, or release evidence.

## 92. 2026-08-11 Docker build override contract

- `docker-compose.yml` now passes `TORCH_INDEX_URL` and `TORCH_REQUIREMENT` as
  build arguments to both the API and queue-worker services. The defaults are
  the CPU Torch index and the project-compatible `torch>=2.7,<3` requirement;
  an intentional GPU build can override them without editing the Dockerfile.
- `.env.example` documents these build-time settings, and the new Docker
  runtime contract tests passed `3` tests. Compose parsing and whitespace
  validation also passed. This makes the image choice configurable but does
  not claim that a full image build completed in the current network.

## 93. 2026-08-11 Academic Writing approval-loop closure

- A fresh authenticated browser run found a real development-path defect:
  the Academic Writing Mock still emitted the older `draft`/
  `citation_checks` shape. The Runtime therefore classified the result as
  structurally incomplete, proposed two replacement plans, and failed closed
  after the bounded replan budget. This was an application contract defect,
  not a browser or SSE failure.
- The Mock profile now emits the current workflow result contract
  (`revised_text`, `revision_notes`, `citation_check`, and
  `unsupported_claims`). Academic Writing also maps a usable citation-review
  result directly to its human approval scope, so approval restores the
  checkpoint without creating a `runtime_plan_proposal` or replaying the
  child Agent.
- The focused Academic Writing and development-Mock group passed `17` tests
  after the fix. The workflow contract fixture was updated to the same
  result fields; no citation is invented and the approval gate remains
  explicit.

## 94. 2026-08-11 cross-role browser acceptance after Academic Writing fix

- One isolated administrator Academic Writing case completed after one
  citation approval: `writing.observe`, `writing.execute`,
  `subagent.execute`, and `writing.verify` were observed; the Runtime used
  one child run, emitted `27` strictly ordered events, and recorded zero page
  errors or failed requests. No plan proposal was created.
- One isolated researcher Academic Writing case completed through the
  researcher workspace after admin-UI account provisioning, with the same
  one-approval/no-proposal behavior and zero page/request errors. The
  researcher role is intentionally denied the teacher debug endpoint (`403`),
  so its report uses the visible task/SSE evidence rather than privileged
  debug data.
- One isolated student LearningLoop case completed the student-facing solver
  task and showed the teaching interaction panel, answer panel, progress
  panel, and runtime controls. The follow-up LearningLoop action reached its
  expected `waiting_approval` state without exposing an approval button to
  the student. Its debug endpoint `403` is expected role isolation, not a
  failed student flow. These are mock-provider application-wiring and UI
  state checks, not semantic or production-provider evidence.

## 95. 2026-08-11 bounded Legacy/Runtime pair after approval-loop fix

- A single isolated API process using a temporary SQLite database ran the
  `lesson_prep_runtime_handoff` and `academic_writing_runtime_handoff` cases
  in both Legacy and Runtime modes, for four total runs. All four completed,
  with zero Agent mismatches and zero event-order failures.
- The Legacy runs emitted `18` and `21` ordered events respectively. The
  Runtime runs each emitted `27` ordered events, reached three Runtime nodes,
  used `13` durable checkpoints, and recorded one explicit approval with zero
  plan proposals. This confirms the corrected quality gate in the public Task
  API path, not only in unit tests or the browser harness.
- The run used the development Mock Provider and automatic development-only
  approval. It is therefore a Runtime handoff/recovery regression, not a
  semantic-quality, external-provider, or release-authorization result.
- The paired-evaluation CLI now normalizes either a host URL or an explicit
  `/api/v1` URL, with a regression test for both forms. This removes an
  operator-only 404 footgun without changing the public API contract.

## 98. 2026-08-11 additional core Runtime pairs

- A second bounded single-API run paired `general_stack_explanation` and
  `assignment_review_runtime_handoff` in Legacy and Runtime modes, four runs
  total. All four completed with zero Agent mismatches and zero event-order
  failures.
- General Question Runtime reached three nodes with `12` checkpoints and
  `22` ordered events. Assignment Review Runtime reached three nodes with
  `13` checkpoints and `27` ordered events, including one explicit approval
  and zero plan proposals. Legacy counterparts completed with `16` and `18`
  ordered events respectively.
- These results extend application/structural Runtime evidence across four
  non-protected business paths when combined with section 95. They still use
  the development Mock Provider and do not constitute semantic parity or
  release authorization.

## 96. 2026-08-11 Docker queue-worker build boundary rechecked

- `docker compose config --quiet` remained valid and the existing Postgres,
  Redis, MinIO, and Qdrant infrastructure containers remained healthy.
- A single `docker compose --profile queue-worker build --pull=false
  --progress=plain queue-worker` attempt was bounded at `180` seconds. It
  produced no queue-worker image and no application container was started.
  The exact Compose/buildx client processes were stopped afterward; Docker
  Desktop and infrastructure containers were left running.
- The reproducible build contract (small context, CPU Torch default,
  BuildKit pip cache, and explicit Torch override arguments) is in place, but
  the current machine still cannot prove a complete image build. This remains
  a deployment-environment dependency/download gate, not a release pass.

## 97. 2026-08-11 provider-free release preflight boundary

- The Lesson Prep release preflight accepted the Agent and Runtime plan
  versions and marked the structural suite eligible, but rejected the
  available semantic material because the sidecar was bound to a different
  suite and the release authorization was not present.
- The existing Academic Writing semantic material is explicitly a model
  preliminary review (`judge_type=model`, `decision=needs_review`) and the
  generated human template remains incomplete. It cannot be promoted to an
  independent semantic pass or release authorization.
- No launch mode, release registry, or semantic gate was weakened. The next
  valid step is an independently reviewed, same-suite semantic sidecar plus a
  version-bound human release decision.

## 99. 2026-08-11 Runtime event persistence and checkpoint deduplication

- Runtime task events are now buffered per Run and flushed in the following
  checkpoint transaction. A focused SQLite regression proves that three
  ordered Runtime events and their checkpoint correlation are persisted with
  one database commit; the event sequence remains `1, 2, 3`.
- Typed child Runs now use the parent TaskRunner checkpoint boundary, so child
  events are not stranded in process memory. The suspension-only event emitted
  after the controller checkpoint receives a final child checkpoint as well.
  The change preserves parent/child lineage and approval/recovery behavior;
  the focused control, child-run, Runtime contract, and observability tests
  passed `37` tests after the checkpoint deduplication change.
- The RuntimeController no longer repeats a terminal/waiting checkpoint that
  PlanExecutor has already persisted. Standalone callers that provide only a
  controller checkpoint hook retain a fallback checkpoint.

## 100. 2026-08-11 General Runtime post-optimization pair and release gate

- A fresh isolated API process and migrated SQLite database ran three
  Legacy/Runtime pairs for `general_stack_explanation` (six runs total).
  All six completed with zero timeouts, zero Agent mismatches, and zero event
  order failures. Runtime traces contain `22` ordered events and `11` durable
  checkpoints per run; the child Run events are present again.
- The current bounded sample averaged approximately `152 ms` for Legacy and
  `686 ms` for Runtime. Runtime control overhead remained approximately
  `146–169 ms`, so the performance gate still reports
  `latency_regression_above_threshold` and
  `single_pair_latency_regression_above_threshold`.
- The evidence packager therefore correctly marks
  `GENERAL_QUESTION_V1` structurally ineligible for release. This is a real
  functional/persistence improvement, not a release pass; semantic review and
  human release authorization remain required after the performance blocker
  is resolved.

## 101. 2026-08-11 Runtime query batching and redundant checkpoint removal

- Runtime checkpoint persistence now reuses the already locked
  `AgentRunModel`, and buffered Task events are allocated as one ordered batch
  instead of re-reading the Task and maximum event sequence for every event.
  Existing row-lock and unique-sequence retry behavior remains in place.
- `PlanExecutor` now skips only a preparation checkpoint whose Run status and
  every node status are unchanged. Node start, completion, failure, approval,
  pause, reconciliation, and terminal metric checkpoints remain durable.
  The focused Runtime contract, parallel recovery, event, and debug tests
  passed `33` tests after this change.

## 102. 2026-08-11 General Runtime bounded performance evidence after dedupe

- A fresh isolated API process and migrated SQLite database ran three
  Legacy/Runtime pairs for `general_stack_explanation` (six runs total). All
  six completed with zero timeouts, zero Agent mismatches, and zero event-order
  failures. Runtime traces retained `22` ordered events and `8` checkpoints
  per completed Run.
- The current sample averaged approximately `175 ms` for Legacy and `535 ms`
  for Runtime. Runtime control overhead was approximately `94–115 ms`.
  This is a material improvement over the earlier bounded sample, but it is
  still above the configured release threshold.
- The provider-free evidence packager therefore still returns
  `latency_regression_above_threshold` and
  `single_pair_latency_regression_above_threshold`. Structural release
  eligibility, independent semantic review, and human authorization remain
  closed.

## 103. 2026-08-11 checkpoint transaction diagnosis and final bounded sample

- A provider-free in-process public-API diagnostic measured the same Runtime
  path without changing repository code or launch configuration. Control
  polling averaged `3.674 ms` across three polls, while eight checkpoint
  transactions averaged `59.111 ms` each (maximum `93.328 ms`). This confirms
  checkpoint persistence, rather than the control query, is the dominant
  remaining Runtime overhead.
- The latest isolated public-API pair repeated the General case three times:
  six runs completed, with `22` ordered Runtime events and `8` durable
  checkpoints per Runtime run. The sample averaged approximately `158 ms`
  for Legacy and `545 ms` for Runtime, with `99–112 ms` Runtime control
  overhead.
- Reusing the already locked Task row in the checkpoint transaction is now
  covered by the existing event/checkpoint tests. The evidence packager still
  fails closed on the two latency regression reasons; no threshold or semantic
  release rule was weakened.

## 104. 2026-08-11 post-commit Lesson Prep browser smoke

- A fresh isolated administrator browser run used the bundled Playwright
  runtime, a temporary SQLite database, the mock Provider, and one API
  process. The authenticated Lesson Prep task completed as
  `TEACH_01_LESSON_PREP_V1` after one visible Runtime approval.
- The report observed `lesson.observe`, `lesson.execute`,
  `subagent.execute`, and `lesson.verify`, with `27` strictly increasing task
  events, three succeeded Runtime nodes, and zero page errors or failed HTTP
  requests. Evidence is stored under
  `.local_outputs/runtime_teacher_browser_acceptance_lesson_prep_20260811_post_commit_retry/`.
- The first attempt exceeded the shell observation window before writing its
  report; the retry completed and released its process and port. This is
  frontend/application-wiring evidence with an explicitly mock Provider, not
  semantic-quality or release authorization evidence.

## 105. 2026-08-11 provider-free release preflight recheck

- The correct `structural_suites/*.json` artifacts from the latest four-case
  evidence package were checked with explicit Agent and Runtime plan versions.
  Lesson Prep, Assignment Review, and Academic Writing each returned
  `structural_eligible=true` with one paired case.
- Those three capabilities remain `release_eligible=false` solely because an
  independently reviewed semantic sidecar is not present. General Question is
  still structurally blocked by the measured latency-regression checks. No
  release threshold, semantic rule, or authorization requirement was relaxed.
- The generated `runtime_canary_manifest.v2` files are collector manifests,
  not direct inputs to the release-preflight schema; the preflight must use
  the packaged `structural_suites/*.json` artifacts. This distinction is now
  recorded to prevent an operator-level false negative.

## 106. 2026-08-11 post-commit General bounded measurement

- A fresh single-API-process, temporary-SQLite run repeated the General
  Legacy/Runtime pair three times. All six runs completed with zero timeouts,
  zero Agent mismatches, and zero event-order failures. Runtime retained
  `22` ordered events and `8` durable checkpoints per run.
- The sample measured approximately `199 ms` average Legacy lifecycle time and
  `564 ms` average Runtime lifecycle time, with Runtime control overhead of
  `93–104 ms`. Compared with the preceding bounded sample (`158 ms` vs
  `545 ms`), the event-sequence reuse change does not establish a material
  latency improvement; the latency release gate remains closed.
- The result validates persistence and ordering after the optimization, but
  no performance claim or threshold relaxation is made. The isolated API
  process and port were released after the run.

## 107. 2026-08-11 checkpoint commit-cost profile

- A provider-free in-process public-API profile captured eight Runtime
  checkpoint calls. They averaged `65.338 ms` and peaked at `83.405 ms`.
- The same profile observed `15` database commits totaling approximately
  `327.790 ms` (maximum `28.147 ms` per commit). This identifies the durable
  transaction/commit boundary as the dominant remaining local cost; the
  earlier event-sequence query was not the limiting factor.
- No asynchronous or non-durable checkpoint shortcut was introduced. Runtime
  recovery semantics and the release latency gate remain unchanged.

## 108. 2026-08-12 current LearningLoop browser recheck

- A fresh isolated authenticated browser run used one API process, a temporary
  SQLite database, the mock Provider, and the current committed code. The
  student-facing `learning_loop` scenario completed its initial
  `ACADEMIC_PROBLEM_SOLVER` task and then completed the
  `teaching_interaction` Runtime after one accepted approval from the
  execution-debug page.
- The run observed the four teaching nodes
  (`teaching.feedback.observe`, `apply`, `verify`, and `approval`), showed the
  answer, teaching-loop, learning-progress, and execution-control panels, and
  produced `39` strictly increasing task events with zero page errors or
  failed HTTP requests. The redacted report is under
  `.local_outputs/runtime_teacher_browser_acceptance_learning_loop_20260812_current/`.
- This confirms current frontend/application wiring and approval recovery for
  the LearningLoop path. It remains mock development evidence and does not
  authorize a canary/default release; the LearningLoop paired structural suite,
  semantic sidecar, and release decision are still missing.

## 109. 2026-08-12 current core-entry browser coverage

- Two additional isolated authenticated administrator runs completed against
  the current committed code with one API process and a temporary SQLite
  database per run. Assignment Review completed as
  `TEACH_02_ASSIGNMENT_REVIEW_V1` after one approval, with three succeeded
  Runtime nodes and `27` strictly increasing task events. Course QA completed
  as `LEARN_01_LOCAL_RETRIEVAL_V1`, with `19` strictly increasing events and
  succeeded `knowledge.execute` and `knowledge.verify` nodes. Both runs had
  zero page errors and zero failed HTTP requests.
- An isolated authenticated researcher run completed Academic Search as
  `RESEARCH_01_ACADEMIC_SEARCH_V1`, with four succeeded research nodes and
  `25` strictly increasing task events. Its attempt to read the administrator
  execution-debug endpoint returned HTTP `403`; this is recorded as the
  intended researcher/admin authorization boundary, not as a task failure.
  The business task and Runtime control projection completed normally, with
  zero page errors and zero failed HTTP requests.
- Reports are stored under
  `.local_outputs/runtime_teacher_browser_acceptance_assignment_review_20260812_current/`,
  `.local_outputs/runtime_teacher_browser_acceptance_course_qa_20260812_current/`,
  and
  `.local_outputs/runtime_researcher_browser_acceptance_academic_search_20260812_current/`.
  These are current mock development/frontend evidence only; they do not
  replace authorized paired traces, semantic review, or release authorization.

## 110. 2026-08-12 LearningLoop checkpoint observability

- The administrator execution-debug projection now includes a redacted
  checkpoint summary for `teaching_interaction` and `learning_progress` Runs:
  checkpoint sequence, Runtime state version, status, correlated Task event
  sequence, and creation time. It deliberately excludes checkpoint
  `state_data`, request snapshots, and student answers.
- The LearningLoop status projection and execution-debug UI now surface the
  snapshot count and latest correlated event sequence. Focused API, redaction,
  UI-contract, Ruff, Mypy, and JavaScript syntax checks passed after the
  change; the focused Runtime/debug tests reported `7 passed`.
- This closes an observability gap for recovery audit and future paired-trace
  collection. It does not change the current LearningLoop release gate: no
  authorized paired suite, semantic sidecar, or human release decision has
  been created.

## 111. 2026-08-11 Lesson Prep approval recovery recheck

- A fresh bounded authenticated browser run used one API process, a temporary
  SQLite database, the development mock Provider, and the current committed
  code. The redacted report is under
  `.local_outputs/runtime_teacher_browser_acceptance_lesson_prep_20260811_quality_gate_recheck/`.
- The task routed to `TEACH_01_LESSON_PREP_V1`, entered
  `waiting_approval`, and completed after exactly one accepted approval. Both
  approval observations reported `plan_proposal_id=null`; no repeated proposal
  was observed after recovery.
- The run observed `lesson.observe`, `lesson.execute`, and `lesson.verify`,
  produced `27` strictly increasing task events, and had zero page errors or
  failed HTTP requests. This is current mock development/browser evidence; it
  is not an authorized paired evaluation, semantic quality decision, or release
  authorization.

## 112. 2026-08-11 Lesson Prep authorized development pair recheck

- A single API process with an isolated temporary SQLite database ran one
  Legacy/Runtime pair for `lesson_prep_runtime_handoff`. Both runs completed;
  the pair summary recorded `2/2` completed, zero timeouts, zero Agent
  mismatches, and zero event-order failures. The redacted report is under
  `.local_outputs/runtime_authorized_dev_e2e_20260811_lesson_prep_pair_after_browser_recheck/`.
- The Runtime run completed after exactly one quality-gate approval. Its
  control record had `proposal_id=null`, the redacted failure diagnostics
  reported zero plan proposals, and the persisted Runtime projection contained
  `10` checkpoints for `lesson.observe`, `lesson.execute`, and `lesson.verify`.
- The Runtime trace contained `27` strictly increasing task events. This is
  stronger paired development evidence for the no-reproposal recovery path, but
  it remains Mock-provider evidence and does not satisfy semantic review or
  release authorization.

## 113. 2026-08-11 Knowledge low-evidence pair boundary

- A single-process pair for `knowledge_capacitor_voltage` completed the Legacy
  run but the Runtime run ended in `failed` after `knowledge.verify` returned
  `knowledge_evidence_insufficient`. The report is under
  `.local_outputs/runtime_authorized_dev_e2e_20260811_knowledge_pair_followup/`.
- Both traces had strictly increasing events and no Agent mismatch. The Runtime
  execution itself produced a retrieval-only artifact and a partial verification
  observation with zero course evidence; it did not create a plan proposal or
  hide the insufficiency. Legacy currently presents the same degraded result as
  a completed task, so this is an explicit Legacy/Runtime semantic status
  difference that remains open for product policy review.
- This failure is retained as fail-closed evidence, not counted as a Runtime
  success and not fixed by weakening the verifier.

## 114. 2026-08-11 Academic Search authorized development pair recheck

- A single API process ran one Legacy/Runtime pair for
  `research_reproducible_evals`. Both runs completed with zero timeouts, Agent
  mismatches, and event-order failures. The redacted report is under
  `.local_outputs/runtime_authorized_dev_e2e_20260811_academic_search_pair_followup/`.
- The Runtime trace used four external-research nodes, retained `10` durable
  checkpoints, and produced `25` strictly increasing events. It recorded an
  `external_retrieval.failed` event for the unavailable development retrieval
  backend, then completed through the declared degraded path with no unresolved
  Runtime failure codes.
- This is Mock/local development evidence for `RESEARCH_01_ACADEMIC_SEARCH_V1`;
  it does not authorize a real Provider, semantic release, or default launch.

## 115. 2026-08-11 LearningLoop teaching interaction paired recheck

- A fresh temporary SQLite database was used to create one synthetic source
  Task under the Runtime profile. After the source Task completed, the API
  process was stopped and restarted on the same database with the Legacy
  profile; the same `request_more_hint` action was then executed through the
  Legacy path. No API/Worker processes overlapped.
- The Runtime action matched the Runtime route and transitioned
  `waiting_approval -> completed` after one accepted approval. All four
  teaching nodes succeeded, the run retained `10` redacted checkpoints, and
  its `39` task events were strictly increasing.
- The Legacy action on the same source Task completed with no Runtime run; its
  route matched Legacy and its `40` task events were strictly increasing. The
  paired reports are under
  `.local_outputs/learning_runtime_authorized_dev_e2e_20260811_runtime_teaching_pair_fresh/`
  and
  `.local_outputs/learning_runtime_authorized_dev_e2e_20260811_legacy_teaching_pair_fresh/`.
- This closes the missing basic paired development trace for the teaching
  interaction adapter. It remains synthetic Mock-provider evidence and is not
  a reviewed semantic sidecar, canary authorization, or default-release
  decision; the LearningLoop readiness gate remains fail-closed.

## 116. 2026-08-11 LearningLoop paired evidence packaging

- Added `scripts/package_learning_runtime_pair.py` and a focused regression
  suite. The packager reads the two public-API reports, validates case/task
  identity, Legacy/Runtime route separation, terminal status, event ordering,
  and Runtime checkpoint ordering, then emits only redacted summaries.
- Packaging the fresh teaching pair produced
  `.local_outputs/learning_runtime_authorized_dev_e2e_20260811_learning_pair_package/learning_runtime_paired_evidence.json`.
  Structural checks passed; the package explicitly retains
  `release_ready=false`, requires a semantic review sidecar and a human
  release decision, and contains no student answer, request snapshot, or
  Runtime state data.
- The packager is evidence governance only. It does not mutate launch modes,
  register authorization, or turn development Mock evidence into canary or
  default-release evidence.

## 117. 2026-08-11 LearningProgress paired recheck

- A fresh serialized single-process run used the same synthetic source Task
  database to execute `learning_progress_manual_review` through Runtime and
  then Legacy. Both actions completed with matching routes and strictly
  increasing events; no API/Worker processes overlapped.
- The Runtime run used the `learning_progress` Runtime, passed all four nodes
  (`observe`, `apply`, `verify`, `approval`), transitioned
  `waiting_approval -> completed` after one approval, and retained `10`
  checkpoints across `55` ordered task events. Legacy completed the same action
  without a Runtime run.
- The redacted pair reports are under
  `.local_outputs/learning_runtime_authorized_dev_e2e_20260811_runtime_progress_pair_fresh/`
  and
  `.local_outputs/learning_runtime_authorized_dev_e2e_20260811_legacy_progress_pair_fresh/`.
  The structural package is
  `.local_outputs/learning_runtime_authorized_dev_e2e_20260811_learning_progress_pair_package/learning_runtime_paired_evidence.json`.
- This confirms the second LearningLoop adapter's development wiring and
  approval recovery. It remains Mock-provider evidence and does not clear the
  semantic sidecar or human release-decision gates.

## 118. 2026-08-11 LearningLoop semantic review intake

- The LearningLoop pair packager now emits a dedicated
  `learning_runtime_semantic_review_intake.v1` section with the four bounded
  semantic dimensions, a `needs_review` judgement template, and an explicit
  requirement for separately redacted domain outputs.
- The teaching and LearningProgress packages were regenerated with
  `status=pending_independent_review`; they contain no raw action payload,
  student answer, request snapshot, or Runtime state data. This is an intake
  template, not a semantic sidecar and not a release authorization.

## 119. 2026-08-11 LearningLoop evidence identity binding

- The redacted pair packager now records the capability ID, Agent version, and
  Runtime plan version selected from the declared LearningLoop Runtime
  contract. The package labels this source as
  `declared_runtime_contract` and keeps `authorization_status=not_authorized`;
  these fields are version-binding metadata, not captured authorization.
- Unknown Runtime `run_kind` values now fail the structural package check with
  `learning_runtime_identity_unknown`, preventing a future semantic sidecar
  from being attached to an unrecognized plan.
- The package remains `release_ready=false` until a separately redacted
  semantic sidecar and independent release decision are supplied. No
  development artifact was promoted by this change.

## 120. 2026-08-11 LearningLoop readiness blocker precision

- LearningLoop capability projections no longer append the generic authorized
  paired-evidence blocker after the structural gate has already passed. They
  now expose the next concrete gate, such as `semantic_evidence_missing` or
  `release_authorization_missing`, while retaining the stable paired-evidence
  blocker for the no-structural-evidence case.
- The change is provider-free and does not widen launch modes. Readiness still
  reports `canary_release_eligible=false` without the complete structural,
  semantic, and authorization chain.

## 121. 2026-08-11 LearningLoop semantic sidecar binding tool

- Added `scripts/collect_learning_runtime_semantic_sidecar.py`. It accepts a
  redacted LearningLoop pair package, private operator inputs/outputs, and a
  separately supplied judgement record. It validates case coverage, capability
  identity, review timezone, redaction status, and the exact judgement schema.
- The emitted `learning_runtime_semantic_sidecar.v1` stores only input/output
  SHA-256 values and semantic judgement metadata; supplied student content and
  action payloads are not serialized. The tool does not call a Provider.
- This adapter intentionally emits
  `learning_runtime_development_paired_evidence_only` and
  `release_ready=false`, even for a human `pass` judgement. A future
  authorized structural suite must still use the existing generic release
  intake and preflight before any canary/default decision.
- Covered by
  `apps/api/tests/test_learning_runtime_semantic_sidecar.py` (6 passed).

## 122. 2026-08-11 frontend publication-gate status correction

- The Agent debug page now treats `release_authorization_missing` as a
  separate final publication blocker. Structural and semantic evidence may
  display as passed, but the overall publication summary and badge remain
  not-ready until the release authorization gate also passes.
- Added a static UI contract assertion and `node --check` validation for the
  browser bundle. The page remains read-only and does not call a readiness
  endpoint or mutate launch configuration.

## 123. 2026-08-11 release preflight rejects LearningLoop development sidecars

- The shared `RuntimeCanaryReleaseRegistry` now recognizes
  `learning_runtime_semantic_sidecar.v1` and rejects it explicitly as a
  development-only sidecar. It cannot be interpreted as a generic authorized
  Runtime semantic sidecar.
- `check_runtime_release_preflight.py` reports the stable blocker
  `semantic_development_evidence_not_authorized`, making the required next
  step visible without weakening the existing generic release gate.
- Registry and preflight regression coverage passed `29` tests. No launch mode
  or release authorization was changed.

## 124. 2026-08-11 multi-case LearningLoop evaluation bundle

- Added `scripts/package_learning_runtime_pair_bundle.py`, which combines
  repeated single-case reports into a stable
  `learning_runtime_paired_evidence_bundle.v1` artifact. It rejects mismatched
  report counts, duplicate case IDs, identity drift, and any case whose
  structural package check fails.
- The semantic sidecar binder now accepts either the existing single-case
  package or the bundle and requires inputs, Legacy/Runtime outputs, and
  judgements to cover every case exactly. It still emits hashes and review
  metadata only, with `release_ready=false` for the development bundle.
- Bundle and multi-case sidecar regression coverage passed `10` tests. This
  expands reproducible evaluation coverage without creating release evidence
  or changing launch modes.

## 125. 2026-08-11 frontend publication-gate behavior regression

- Added a Node-backed behavior test that evaluates the real `agents.js`
  publication projection in isolation, without an API, Provider, or browser.
- The test confirms a fully authorized readiness payload is publish-ready and
  a payload with `release_authorization_missing` is not publish-ready even
  when structural and semantic evidence are both true.
- Static UI contract plus behavior coverage passed `11` tests; `node --check`
  also passed.

## 126. 2026-08-11 development launch-mode and capability audit

- Audited the development launch profile against the registered non-Xingchen
  Task Runtime services. The default list covers the active solver, general
  question, local retrieval, teaching, academic search, and academic writing
  Runtime adapters.
- Confirmed that `LEARN_01_KNOWLEDGE_QA_V1` remains the cloud/legacy registry
  identity while `LEARN_01_LOCAL_RETRIEVAL_V1` is the local Runtime fallback;
  the distinction is reflected in the existing routing and Runtime tests and
  is not a launch-mode defect.
- Confirmed that `RESEARCH_03_DATA_ANALYSIS_V1` is not part of the implicit
  development launch profile. Its protected migration remains explicit and
  was not inspected or changed in this audit.
- Launch policy, Task-to-Runtime handoff, and cross-entry readiness regression
  coverage passed `42` tests. No service was started and no release gate was
  weakened.

## 127. 2026-08-11 Lesson Prep single-case post-fix E2E

- Re-ran the isolated `lesson_prep_runtime_handoff` Legacy/Runtime pair on a
  single local API instance after the empty-quality-section fix.
- Both runs completed: `2/2` completed, `0` timeouts, `0` Agent mismatches,
  and `0` event-order failures. The Runtime run captured exactly one quality
  approval and finished with `runtime_status=completed`.
- The Runtime result reported `plan_proposal_count=0` and no
  `runtime_plan_proposal` event. This is the targeted evidence that the
  approval no longer causes a duplicate proposal loop for this case.
- The redacted report is retained under the ignored `.local_outputs/` path;
  the API instance was stopped immediately after the run.

## 128. 2026-08-11 non-protected Runtime paired evaluation after fix

- Re-ran the seven non-protected Task Runtime cases as alternating
  Legacy/Runtime pairs: general question, local retrieval, solver, academic
  search, Lesson Prep, assignment review, and academic writing.
- All `14/14` runs completed with `0` timeouts, `0` Agent mismatches, and `0`
  event-order failures. Every result reported `runtime_status=completed` and
  `plan_proposal_count=0`; the two quality-review cases recorded one approval
  each where required.
- `RESEARCH_03_DATA_ANALYSIS_V1` was intentionally excluded from this batch;
  its protected source and dedicated tests remain outside this migration
  slice. The API instance was stopped after the report was written.

## 129. 2026-08-11 browser acceptance attempt

- The API was started on the isolated development port for a frontend
  acceptance pass, but the in-app browser transport closed during browser
  initialization before any page interaction; this attempt produced no new
  browser result.
- The API instance was stopped after the failed connection attempt. This does
  not invalidate the earlier redacted browser reports already retained under
  `.local_outputs/`.

## 130. 2026-08-11 browser evidence inventory reconciliation

- Existing private reports record completed browser-driven flows for the
  Workspace and for Lesson Prep, Assignment Review, Academic Search, Academic
  Writing, and LearningLoop scenarios. The reports include visible task
  status, Runtime controls, terminal result rendering, and ordered event
  summaries; approval-gated scenarios record the visible approval transition.
- Both Mock and selected `real_local` provider profiles are represented. These
  are development acceptance artifacts, not production semantic review or
  release authorization.
- The current browser transport retry remains unverified, but the overall
  frontend evidence is therefore `partially verified`, not “no browser
  acceptance”.

## 131. 2026-08-11 release-default audit and final governance regression

- Audited `.env.example`, `Settings`, and the development launcher together:
  production defaults keep `AGENT_RUNTIME_RELEASE_GATE_REQUIRED=true`, empty
  launch/evidence/authorization paths fail closed, and the implicit Runtime
  profile is limited to development/test environments.
- The final provider-free governance regression passed `118` tests covering
  canary collection/release evaluation, semantic evidence intake, release
  authorization, readiness projections, launch policy, UI publication gating,
  and the single-instance launcher. No API or worker was started for this
  check.
- The remaining production decision is intentionally external: an authorized
  semantic review and a version-bound human release authorization must be
  supplied before any canary/default promotion.

## 132. 2026-08-11 real-browser control prerequisite diagnosis

- A real Microsoft Edge window did open the formal Workspace page; its window
  title was `智能任务工作台 · 芯智导学`. The local API page itself was therefore
  reachable, but no interactive browser evidence was collected in this pass.
- The browser diagnostic reported the selected Edge profile with
  `Installed: no` and `Enabled: no` for the Codex browser extension. The native
  host diagnostic also reported that
  `C:\Users\86184\AppData\Local\OpenAI\extension\com.openai.codexextension.json`
  and the corresponding user registry key were absent.
- Chrome extension diagnostics were additionally interrupted by a UTF-8 BOM
  parse error in the selected profile configuration. These are browser-control
  prerequisites, not application acceptance results. The formal frontend
  student/teacher/researcher click-through remains pending until the extension
  and native host are restored.

## 133. 2026-08-11 real Edge frontend acceptance after extension installation

- The installed Edge extension and native host passed diagnostics. A single
  development API/Worker instance was started on `127.0.0.1:8031`; all browser
  interactions below used the formal frontend in real Microsoft Edge.
- Student path: the empty-input validation displayed `请输入题目或上传材料`;
  a circuit question then streamed visible recognition, planning, execution,
  and Runtime status updates and rendered a completed answer of `1 A`. The UI
  correctly marked this result as a fallback with `accepted_with_warnings`, so
  it is not treated as high-confidence semantic evidence.
- Teacher/admin path: the teacher workspace opened successfully as a guest;
  a synthetic local administrator account was used for the authorized approval
  test. Lesson Prep visibly entered `等待人工审批`; submitting `提交审批`
  displayed the resume toast and the lesson plan subsequently rendered with
  Runtime status `已完成`. No repeated proposal was visible in the UI. The
  duplicate-proposal assertion remains covered by the backend E2E report in
  section 127, rather than inferred from the browser alone.
- Researcher path: a synthetic local researcher account created through the
  Admin UI opened the research workspace. `科研前沿检索` completed with a
  six-paper evidence brief, visible evidence limitations, source identifiers,
  and `已完成 · 使用后备路径`. After reload, the session remained in the
  session list and clicking it restored the result and source panel; the page
  does not auto-select the last session on reload.
- No application console errors were observed on the student or teacher tabs.
  The admin/researcher tabs contained only `Could not establish connection.
  Receiving end does not exist`, which is emitted by the browser extension
  integration and was not accompanied by a page failure. Synthetic account
  credentials and test data are not committed. The single API/Worker instance
  is stopped after this acceptance pass.

## 134. 2026-08-11 real Edge evidence-panel regression and fix

- A fresh formal Workspace task reproduced the reported issue before the fix:
  the answer contained inline `查看证据 S1/S2/S4` references, while the
  `资料依据` panel incorrectly reported that no evidence was available and
  showed a zero source count.
- Root cause: Runtime results stored usable evidence in
  `structured_result.core_retrieval_summary` (and, for other Runtime shapes,
  `knowledge.hits` or `evidence_packet.sources`), but terminal presentation
  only built cards from the legacy workflow context bundle. The frontend
  renders the panel from `structured.evidence_view`, so valid Runtime evidence
  was present in the result but never converted into view cards.
- Fix: `task_presentation.py` now converts the supported Runtime evidence
  shapes into validated `KnowledgeHit` values, preserves evidence IDs/source
  references, and derives the same `EvidenceViewItem` cards and counts used by
  the legacy path. The conversion selects contract fields instead of
  forwarding Runtime-only fields that the strict `KnowledgeHit` model rejects.
- Regression coverage now includes both `knowledge.hits` and the actual
  `core_retrieval_summary` shape. Targeted Ruff, Mypy, and Pytest checks pass
  (`14 passed`).
- Real Edge revalidation on a fresh post-fix task displayed `使用 5 条课程资料`
  and five visible cards (S1-S5), each with `打开资料`. Opening S1 displayed
  the original read-only course document, chapter path, cited excerpt, and a
  successful document-page request. Persisted tasks created before this fix
  can retain their old empty `evidence_view`; they must be rerun to regenerate
  presentation data.

## 135. 2026-08-11 real Edge multi-domain pass and stale-answer fix

- Student circuit-analysis path: a fresh Workspace task for `10V` in series
  with `5Ω` completed with a visible `2 A` result, KVL derivation, unit and
  power checks, Runtime status `已完成`, and the explicit warning that the
  conclusion had not received full deterministic verification. The persisted
  task API also reported `completed`, `provider=local_graph`, and one real
  Spark model call; it was not treated as a fully verified answer.
- A second task exposed a frontend state issue: while a new task was running,
  the previous circuit answer remained visible. The cause was
  `markAnswerPending()` changing only status text while leaving answer,
  notices, business view, and evidence DOM intact. It now clears those regions
  before the new task stream begins, and the static resource build ID was
  advanced to invalidate cached Workspace scripts.
- Real Edge revalidation after the cache-busting change confirmed that a new
  task showed `正在组织回答` without the previous circuit or capacitor answer.
  The completed task then restored the expected three cited course materials.
- Teacher workspace path: `/teacher` opened in guest mode, CT filtering and
  `查询指标` completed successfully, and the page rendered course material
  quality, PDF/OCR review, CT/AE error-template review, and course-asset
  readiness panels. No student personal data was shown. Protected teacher
  approval/resume execution remains the next browser pass.

## 136. 2026-08-11 real Edge multi-domain continuation and session-state fix

- A synthetic local administrator account was provisioned only for this local
  acceptance pass. It was used through the formal Edge login page; no password
  or account artifact was committed.
- Authorized Teacher Workspace flows completed in real Edge:
  - Lesson Prep entered `waiting_approval`; `提交审批` resumed the checkpoint,
    rendered the lesson-plan answer, and ended in `completed`.
  - Assignment Review required an adaptive plan decision; after
    `应用恢复计划` it rendered a teacher-review-only draft and explicitly did
    not issue a formal grade.
  - Academic Writing required two adaptive plan applications before it
    completed. The final result displayed the rewrite, citation/fact
    verification warning, and no invented measurements or citations. The
    intermediate second proposal is recorded as a Runtime replan observation,
    not counted as a Lesson Prep quality-gate duplicate.
  - Academic Search completed after external retrieval and displayed two
    arXiv evidence items, source identifiers, links, and explicit preprint and
    evidence-limit warnings in the source panel.
- Guest Workspace testing exposed a separate UI defect: starting a
  quality-gated task and then selecting `新建会话` cleared the conversation but
  left the new session's input and send controls disabled while no cancellable
  task was attached to the page. `resetConversation()` now explicitly calls
  `setBusy(false)`, and a static regression test covers this contract.
- Real Edge revalidation after the patch confirmed both the question textbox
  and `发送问题` were enabled in the newly created session. The build ID was
  advanced to invalidate cached Workspace assets.
- The protected `RESEARCH_03_DATA_ANALYSIS_V1` path was not opened, inspected,
  or executed. Only the non-protected Academic Search and Academic Writing
  paths were tested in this continuation.

## 137. 2026-08-11 real Edge checkpoint reload, resume observation, and evidence text rendering

- A real Edge pause/reload pass reproduced a frontend recovery gap: after a
  persisted Runtime checkpoint was refreshed, the conversation was restored but
  the Runtime control surface was missing. `loadSessionHistory()` only resumed
  `created`, `queued`, and `running` tasks, so `paused`, `waiting_user`, and
  `waiting_review` checkpoints were not rendered.
- The Workspace now renders a persisted checkpoint, reloads its Runtime control
  projection, and re-establishes task/SSE observation after `resume`, `approve`,
  or `input`. Static UI tests cover both the checkpoint status set and the
  resumed-task observer.
- Real Edge revalidation confirmed the full path: a paused task reloaded with
  `已暂停` and `恢复`; after clicking `恢复`, the page showed the running
  controls, later rendered the completed answer, and ended with terminal Runtime
  controls disabled. The run produced six external evidence cards.
- The same evidence panel exposed a separate presentation defect: one of six
  external abstracts contained literal HTML entities such as `&amp;lt;`. The
  card renderer now decodes up to two layers of HTML entities into text before
  display, without using HTML injection. After cache-busted reload, Edge showed
  six cards with zero encoded-entity anomalies and valid DOI/arXiv links.
- Verification completed for the changed UI surface: targeted Pytest (`2
  passed`), Ruff, JavaScript syntax check, and `git diff --check`. The full
  multi-domain frontend audit remains in progress; the protected research-data
  path remains excluded.

## 138. 2026-08-12 real Edge Lesson Prep retrieval-to-evidence regression fix

- A real authenticated Edge Teacher task reproduced the reported evidence
  presentation gap: the TEACH_01 registry enabled local RAG, but the completed
  lesson showed `未使用课程资料` and no evidence cards after approval.
- Root cause was in the Runtime handoff rather than the course index. The
  default Runtime request carried `execute` but not an explicit `retrieve`
  flag, so the typed business Runtime did not create its retrieval node from
  the immutable execution plan. The typed sub-agent also received no local
  retrieved context, and the bounded hits were not persisted into the final
  `AgentResult` for task presentation or checkpoint recovery.
- The fix makes the general typed Runtime honor `_execution_plan.use_rag`
  unless an explicit per-runtime `retrieve` value is present; it injects the
  bounded local context into the internal-agent input; and it stores validated
  retrieval hits in `structured_result.knowledge.hits`, including trace and
  index metadata. The frozen solver adapter remains unchanged.
- Task presentation now distinguishes `已检索 N 条课程资料` from
  `未使用课程资料` when cards exist but the answer has no explicit citation
  IDs. This avoids claiming unsupported direct citation while making the
  available evidence visible for teacher review.
- Real Edge revalidation completed the authenticated teacher flow: new lesson
  task, `等待人工审批`, `提交审批`, checkpoint resume, terminal completion,
  five course evidence cards (S1-S5), and `打开资料` source dialog with the
  read-only course excerpt. Targeted Runtime and presentation regression tests
  pass (`27 passed`); the full frontend multi-domain audit remains in progress.
## 139. 2026-08-12 real Edge multi-domain audit continuation and review-status rendering fix

- Real Edge student coverage completed for Circuit Theory, Analog Electronics, and Digital Electronics knowledge questions. Each answer completed with course evidence indicators and inspectable source references.
- The frozen Circuit Solver path completed a numerical circuit task and kept its method-reference-only boundary; it did not present solver output as a cloud-backed course citation.
- Guest Academic Search completed with six paper evidence items, DOI/source links, and explicit evidence-limit warnings. Guest Academic Writing correctly stopped at `waiting_approval` without exposing an approval control.
- Authorized Teacher Assignment Review completed after approval and displayed five course evidence cards, teacher-only feedback, and the non-grading notice. Authorized Academic Writing also completed after approval and displayed a cautious rewrite plus fact/citation verification warnings.
- The Assignment Review result exposed a frontend defect where the business field `人工复核` rendered the raw boolean `true`. `businessValueText()` now maps review booleans to `需要人工复核` or `无需人工复核`; the Workspace build ID and static regression expectations were advanced accordingly.
- Post-patch real Edge revalidation showed `需要人工复核`, no standalone raw `true`, successful approval recovery, and terminal completion. The complete frontend audit and protected research-data path remain unfinished/excluded.
