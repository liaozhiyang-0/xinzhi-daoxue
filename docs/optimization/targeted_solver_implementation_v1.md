# 统一学术求解器定向优化实施说明 v1

## 1. 实施结果

本轮在现有 `ACADEMIC_PROBLEM_SOLVER` 内增加请求预算、复杂度策略、受控回退、
AE/DE 确定性验证、REVIEW/VERIFY 和边界策略。没有建立第二套运行时，没有
修改工作流 ID、现有 Provider 环境变量或冻结的 `SOLVER_CT v1.0`。

开发分支为 `improve/targeted-solver-optimization-v1`。创建分支时工作区已有
大量未提交的教学闭环第一至第三阶段文件；本轮没有覆盖、删除或重置这些文件。
部分共享文件同时包含用户原有修改与本轮增量，因此当前没有为本轮强行拆分提交。

## 2. 请求时间预算与复杂度

`solver_runtime_policy.py` 提供：

- `RequestTimeBudget`：140 秒软截止、165 秒最终整理、175 秒硬截止；
- 单调时钟计算，不受系统时钟回拨影响；
- 软截止后不再启动图片汇总、续写或二模型验证等可选调用；
- 最终整理阶段保留已有确定性结果和部分答案；
- `simple`、`medium`、`complex`、`high_risk` 的规则分类；
- SOLVE/REVIEW/VERIFY 对应的生成调用预算。

三个截止值可通过以下兼容环境变量调整：

```text
ACADEMIC_SOLVER_SOFT_DEADLINE_SECONDS
ACADEMIC_SOLVER_FINALIZATION_DEADLINE_SECONDS
ACADEMIC_SOLVER_HARD_DEADLINE_SECONDS
```

Provider 原有单调用 timeout 参数保持不变；请求预算由服务外层
`asyncio.timeout` 提前取消，以兼容已有 Provider 调用契约。

## 3. 条件验证与结果保留

`AcademicProblemSolverService` 只在以下情况触发验证判断：

- 用户明确请求验证或使用 VERIFY；
- 专业验证器发现冲突；
- complex/high_risk；
- 置信度低；
- 结构化输入存在不确定或冲突。

简单题不默认进入大模型二次验证。专业验证发现冲突时，追加受影响步骤、
建议修正和风险，保留未受影响答案，并设置 `requires_regeneration=false`。
主模型超时或异常时，服务保留 Graph 已生成的确定性部分，不把整份答案清空。

短多图题不再仅因缺少内部完成标记重复生成整份答案。只有超长综合题会使用
完成标记辅助判断；Provider 明确报告长度截断时仍允许有界续写。

## 4. 回退治理

新增 `FallbackReason` 与 `FallbackTracker`：

- 记录 `source_agent`、`target_agent`、`fallback_reason`、
  `fallback_stage`、`fallback_count`；
- 默认最多允许一次回退；
- 目标已在 `route_path` 中或来源不是当前路径尾节点时拒绝，阻止环路；
- 模型路由 fallback 在 `ModelResponse.raw_metadata` 中标注来源和目标；
- 后续图片、汇总、生成调用会关闭再次模型路由 fallback；
- TaskRunner 只执行明确批准且 `fallback_count == 1` 的旧 CT 基线。

普通 CT 文本题和可恢复结构的一般图片题继续走统一求解器。格式和展示问题由
本地适配处理，不再作为旧 CT 专业基线的充分触发条件。

## 5. AE 专业验证

课程注册表新增并兼容以下标签：

```text
dc_bias
bjt_small_signal
mos_small_signal
op_amp
feedback
frequency_response
power_amplifier
waveform_generation
comparator
regulated_power_supply
```

`AEValidator` 当前确定性覆盖：

- 静态工作点中混入交流等效或中频增益；
- BJT `V_BE` 与放大区假设冲突；
- MOS `V_GS <= V_TH` 却使用强反型饱和区公式；
- 理想运放虚短缺少线性负反馈条件；
- 共射/共源中频增益遗漏反相负号；
- 信号源电压增益遗漏输入分压。

冲突结果包含类型、影响步骤、证据和局部修正建议，不自动重写整份答案。

## 6. DE 专业验证

`DEValidator` 提供：

- 1–8 个变量的安全 AST 布尔表达式解析；
- 全真值表枚举和首个反例；
- 按初态、输入、触发沿、转移表逐周期模拟；
- 算术右移补零冲突；
- 时序状态被描述为连续更新的冲突。

表达式只接受受控布尔语法，不执行任意 Python 代码。状态转移表缺项、空状态和
非法触发沿会明确报错。

## 7. REVIEW 与 VERIFY

`AcademicProblem.task_mode` 新增 `SOLVE|REVIEW|VERIFY`，默认值为 `SOLVE`，
旧请求无需修改。

REVIEW 按学生步骤顺序输出：

- 整体状态；
- 第一处实质错误步骤；
- 错误类型；
- 错误原因；
- 正确写法；
- 对后续步骤的影响；
- 此前仍有效的步骤。

VERIFY 只把 `verify_target` 作为待审查步骤，不自动扩展为无关长篇回答。
当前规则覆盖电路参考方向、二极管线性误用、反馈环路增益、阈值逻辑、CMOS
功耗平方关系、随机变量二阶矩、奈奎斯特条件、Z 变换共轭、平稳与遍历性、
通信游程等定向类型。

## 8. 确定性边界策略

模型调用前拦截：

- 缺电路图或引用题上下文；
- 缺公式正文或收敛域；
- DE 未知/高阻态却要求唯一二值；
- DE 计数器缺初态、触发沿和连接；
- 运放虚短缺少线性负反馈条件；
- 定理前提未知却要求无条件结论；
- 非法概率分布；
- 同一参考方向下互相矛盾的功率要求。

边界结果复用现有 `status`、`confidence`、`assumptions` 和风险字段，并在
`boundary_decision` 中给出 `answer_status`、`can_continue`、
`missing_information`、`uncertain_points`。依赖假设的绝对化表述会被改写为
条件化表述。

## 9. 可观测性

`solver_observability` 和兼容的 `RunMetrics` 增加默认字段：

```text
request_id, course, task_mode, complexity, route_path,
fallback_reason, fallback_count, model_call_count, rag_call_count,
vision_call_count, verification_triggered, verification_reason,
time_budget_exhausted, deadline_remaining_ms, partial_result_available,
verification_skipped_reason, node_timings
```

节点记录 ID、耗时、状态、模型和错误类型。不记录 API 密钥、完整学生文本或
不必要的身份信息。

## 10. 文件清单与公共接口影响

| 文件 | 变更 | 公共接口 |
|---|---|---|
| `.env.example` | 增加三个请求预算示例变量 | 仅配置示例，兼容 |
| `contracts/solver.py` | 模式、复杂度、回退、验证、审查和观测契约 | 仅新增默认字段/类型 |
| `contracts/agent.py` | `RunMetrics` 增加默认观测字段 | 兼容旧响应 |
| `contracts/__init__.py` | 导出新契约 | 新增导出 |
| `core/config.py` | 请求截止时间配置 | 默认值兼容 |
| `courses/registry.py` | 扩展 AE 标签并保留原分类优先级 | 课程 ID 不变 |
| `solver_runtime_policy.py` | 时间预算、复杂度、回退账本 | 内部新模块 |
| `solver_boundary_policy.py` | 代码层边界决策 | 内部新模块 |
| `ae_validator.py` | AE 有限确定性验证 | 内部新模块 |
| `de_validator.py` | DE 逻辑与状态验证 | 内部新模块 |
| `academic_review.py` | REVIEW/VERIFY 第一错误审查 | 内部新模块 |
| `academic_solver_service.py` | 将上述能力接入统一链路 | 保持 AgentResult 旧字段 |
| `model_service.py` | 单请求模型 fallback 控制与元数据 | 内部保留字被调用层剥离 |
| `task_runner.py` | 旧 CT 基线只接受明确回退决策 | 任务 API 不变 |
| `student_verification.py` | 步骤级第一错误定位 | 教学反馈更精确 |
| `solution_packet_adapter.py` | 传递题目摘要 | 默认值兼容 |
| `test_targeted_solver_optimization.py` | 单元、契约、私有定向回归 | 测试文件 |

## 11. 运行与验证

定向测试：

```powershell
.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_targeted_solver_optimization.py `
  apps/api/tests/test_universal_academic_solver.py `
  apps/api/tests/test_solution_packet_adapter.py `
  apps/api/tests/test_teaching_loop_phase2_services.py -q --no-cov
```

提交前检查：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

没有执行 336 例完整 live 测试，也没有调用真实 Provider。完整准确率、真实
P90/P95 和课程回退率变化必须在用户批准后另行验证。

## 12. 安全回滚

待形成审查通过的提交后：

```bash
git log --oneline
git revert <commit>
```

不得使用 `git reset --hard` 或 `git checkout --` 覆盖当前未提交的教学闭环
代码。
