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
