# Runtime 工作台解题链路验收记录（2026-08-10）

## 结论

已在授权的开发环境中，从现有浏览器工作台完成一次真实的“前端输入 → Task API → SSE 进度 → Agent Runtime → 前端结果渲染”解题链路验证。该任务进入的是 `ACADEMIC_PROBLEM_SOLVER` 的业务 Runtime，而非 `compat-1` 或 Legacy 包装计划；四个计划节点均成功结束，页面正确展示了计算结论、公式与自检内容。

本记录只证明开发环境下的一次端到端可用性，不构成语义等价、性能达标、canary/default 发布或人工发布决定。`SOLVER_CT v1.0` 未修改，星辰工作流未调用。

## 验收范围与授权边界

- 环境：本机开发环境，使用现有环境变量；启动时显式使用 `--runtime-dev`。
- Agent：`ACADEMIC_PROBLEM_SOLVER`，本地学术求解路径；不包含星辰工作流。
- 输入：一条脱敏、合成的基础电路欧姆定律题；原始输入、Task ID、运行 ID、完整输出、SSE 负载和 checkpoint 状态不写入仓库。
- 数据与密钥：未写入 `.env`，未展示或提交任何 Provider 凭据、Flow ID 或私有运行工件。
- 发布边界：该启动档案仅在显式开发参数下解除本地 Runtime release gate，正常启动仍保持 fail-closed；本次未设置任何 Agent 为默认路径。

## 实际观察结果

| 检查项 | 结果 |
| --- | --- |
| 工作台入口 | `GET /workspace` 可访问，游客模式可创建会话并提交任务 |
| 路由目标 | `ACADEMIC_PROBLEM_SOLVER` |
| Runtime 标识 | `run_kind=runtime` |
| 计划版本 | `solver-runtime-v1` |
| Runtime 状态 | `completed` |
| 节点执行 | `solver.observe`、`solver.retrieve`、`solver.execute`、`solver.verify` 全部 `succeeded` |
| 事件/状态 | 23 个 Task 事件，序号连续递增；15 个持久化 checkpoint |
| 结果呈现 | 页面展示 `2 A` 的结论、KVL/欧姆定律推导、KCL/KVL 与参考方向自检；数学公式已渲染 |
| Legacy 回退 | 无；最终 `fallback_reason` 为空 |

此前也已在同一工作台对本地知识问答路径完成一次真实输入验证，确认 Runtime 详情、节点、预算、checkpoint 与后备路径提示不会互相误标。该结果记录在既有的授权开发 E2E 文档中；本次补充的是求解器路径的浏览器可用性证据。

## 可复现方式

在仓库根目录以 PowerShell 运行：

```powershell
.\.venv\Scripts\python.exe scripts\team_launcher.py start `
  --runtime-dev --force-reload --port 8000
```

然后在浏览器打开 `http://127.0.0.1:8000/workspace`，提交一条不含学生隐私、密钥或星辰 YAML 的基础电路题。完成后可在 `http://127.0.0.1:8000/debug/execution` 查看任务的 Runtime 投影；公开文档只记录汇总，不复制私有 trace。

开发档案会显式启用以下本地业务 Runtime：

```text
ACADEMIC_PROBLEM_SOLVER=default,
GENERAL_QUESTION_V1=default,
LEARN_01_LOCAL_RETRIEVAL_V1=default
```

## 已执行的自动化验证

本次工作台验收前已通过以下相关检查（不包含 RESEARCH_03）：

```powershell
.\.venv\Scripts\ruff.exe check scripts\team_launcher.py `
  apps\api\tests\test_team_launcher.py `
  apps\api\tests\test_runtime_task_execution_path.py

.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_team_launcher.py `
  apps/api/tests/test_academic_solver_runtime.py `
  apps/api/tests/test_runtime_controls.py `
  apps/api/tests/test_runtime_task_execution_path.py::test_academic_solver_runtime_path_keeps_solver_graph_behind_runtime `
  apps/api/tests/test_runtime_task_execution_path.py::test_general_question_runtime_default_launch_mode_requires_no_runtime_option `
  apps/api/tests/test_runtime_task_execution_path.py::test_local_retrieval_runtime_default_launch_owns_learning_task
```

结果：23 项通过（有两条既有警告）。浏览器验收为真实本地开发调用，不是 mock；Docker、预发/生产依赖、独立语义评审与发布演练均未执行。

## 待人工审核与发布决定

下列事项不能由本记录、自动化测试或模型初审替代：

1. 使用受控私有工件对同一输入完成 Legacy/Runtime 的独立语义评审，填写评审人、日期、风险与结论。
2. 对求解器的性能波动完成单独调查；历史受控配对中存在超过阈值的延迟回归，因此当前仍应保持 Legacy/fail-closed 的发布状态。
3. 由发布责任人决定继续灰度、设为默认或回滚；不得仅因本地工作台 E2E 成功而切换默认。
4. 在预发等价环境完成数据库、worker、Redis/MinIO、SSE 重连与 Docker 演练后，再评估生产就绪性。

相关的证据收集合同、授权配对记录、AI 初审记录与代码完成审计见：

- [证据 intake 合同](runtime_evidence_intake_contract.md)
- [授权开发配对记录](runtime_authorized_dev_e2e_2026-08-10.md)
- [AI 语义初审记录](runtime_ai_preliminary_semantic_review_2026-08-10.md)
- [Runtime 代码完成审计](runtime_completion_audit_2026-08-10.md)
