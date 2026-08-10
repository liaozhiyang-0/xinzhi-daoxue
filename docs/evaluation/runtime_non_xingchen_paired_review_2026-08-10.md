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
| `TEACH_01_LESSON_PREP_V1` | 完成 | `waiting_approval` 超时 | 23--24 个事件，13--14 个 checkpoint，3 个节点 | 不通过；首次子 Agent 结构化输出为 `StructuredOutputError`，暴露失败 child 复用问题 |
| `TEACH_02_ASSIGNMENT_REVIEW_V1` | 完成 | 完成 | Legacy 18/2；Runtime 27/13，3 个节点 | 结构与前后端链路通过；语义仍需人工复核 |
| `RESEARCH_02_ACADEMIC_WRITING_V1` | 完成 | 一次完成，一次 `waiting_approval` 超时 | 成功样本 27/13；失败样本 24/13，3 个节点 | 不稳定；不能作为默认发布依据 |

说明：所有已完成 Runtime 样本均确认 Agent ID 匹配、事件序列严格递增，且结果 artifact 可被原应用结果视图读取。`waiting_approval` 不代表成功；它表示 Runtime 保留了可恢复状态并等待控制。

## 3. 私有证据位置

以下目录已被忽略，不应提交到公共仓库：

- Assignment Review 配对：[report.json](C:\Users\86184\Desktop\xinzhi-daoxue\.local_outputs\runtime_authorized_dev_e2e_20260810_assignment_review_pair\report.json)
- Academic Writing 成功 Runtime：[report.json](C:\Users\86184\Desktop\xinzhi-daoxue\.local_outputs\runtime_authorized_dev_e2e_20260810_academic_writing_runtime\report.json)
- Academic Writing 配对重试：[report.json](C:\Users\86184\Desktop\xinzhi-daoxue\.local_outputs\runtime_authorized_dev_e2e_20260810_academic_writing_pair\report.json)
- Lesson Prep 配对：[report.json](C:\Users\86184\Desktop\xinzhi-daoxue\.local_outputs\runtime_authorized_dev_e2e_20260810_lesson_prep_pair\report.json)
- Lesson Prep 修复前后验证：[report.json](C:\Users\86184\Desktop\xinzhi-daoxue\.local_outputs\runtime_authorized_dev_e2e_20260810_lesson_prep_runtime_retry4\report.json)

前端原应用成功链路的浏览器证据见：[runtime_non_xingchen_application_e2e_2026-08-10.md](C:\Users\86184\Desktop\xinzhi-daoxue\docs\evaluation\runtime_non_xingchen_application_e2e_2026-08-10.md)。该证据覆盖输入、Task、SSE、Runtime、外部检索和结果视图，但不替代语义等价评审。

## 4. 自动预审记录

评审人标识：`Codex automated structural review`  
评审日期：2026-08-10  
评审类型：结构、生命周期、事件顺序、结果契约和前后端展示链路预审；不是独立人工语义评审。

### 4.1 通过项

- Task 创建保持非阻塞，Provider 调用未放入路由请求线程。
- Runtime 已产生可恢复的 plan、节点状态、checkpoint、控制事件和结果 artifact。
- 已完成样本的事件序列严格递增，Legacy/Runtime 的目标 Agent ID 匹配。
- Assignment Review 已完成一次 Legacy/Runtime 全流程配对。
- `runtime_child_run.py` 的失败 child 不再无限复用：失败且没有结果的 child 会在有界重规划时创建新的 durable child；新增回归测试已通过。

### 4.2 未通过项与风险

- Lesson Prep 的本地模型结构化输出可能返回 `StructuredOutputError`；Runtime 会安全停在审批/重规划状态，但当前业务不能稳定产出结果。
- Academic Writing 出现一次成功、一次结构化输出失败，说明当前模型/结构化输出链路仍有波动。
- 自动审批仅用于开发链路验证，不能替代教师、研究负责人或发布责任人的语义判断。
- 本轮未证明 Legacy 与 Runtime 的语义等价性，也未证明可设为生产默认。

## 5. 发布决定模板

### 自动建议

建议：**继续开发环境灰度，暂不设为默认，暂不发布生产**。  
理由：Assignment Review 链路通过，但 Lesson Prep 未通过且 Academic Writing 稳定性不足；当前证据不能支持全范围默认切换。

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

1. 重启并确认 API 加载 child retry 修复后，重新跑 Lesson Prep；至少取得连续 3 次 Runtime 完成样本。
2. 对 Lesson Prep 和 Academic Writing 各做独立语义评审，逐对记录等价性、质量和风险。
3. 只有在语义评审、前端显示检查和责任人发布决定均完成后，才考虑扩大灰度。
