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
  the development mock profile and `--auto-approve-dev`. The private report is
  under `.local_outputs/runtime_authorized_evidence_20260811_lesson_runtime_final/`.
- The run reached the first plan-proposal approval and resumed with strictly
  increasing events, but then failed closed after the resumed execution hit
  `ProviderNotConfiguredError` / `ProviderUnavailableError` in the local
  subagent path. The subsequent proposal candidate exceeded the remaining
  subagent budget; the task ended with `conflict`, 21 checkpoints, and no
  second pending proposal event. This is a reproducible development diagnostic,
  not a passing E2E result.
- The result confirms the approval checkpoint itself is durable and applied,
  while the post-approval provider/budget path still needs a dedicated fix or
  an explicitly configured provider profile before Lesson Prep can be called
  complete. No Runtime-wide or release conclusion is drawn from this failure.
