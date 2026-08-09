# Runtime 授权成对 trace 采集与发布决策 Runbook

本文是一次真实 Runtime canary 评测的操作手册，适用于已经完成代码、配置和权限审查的 Agent。它描述“如何采集和判定证据”，不声称仓库已经拥有真实生产 trace，也不自动执行 Provider、模型、工具调用或发布操作。

## 0. 不可绕过的边界

- `scripts/collect_runtime_canary.py`、`scripts/collect_runtime_semantic_evidence.py`、`scripts/evaluate_runtime_canary.py` 和 `scripts/check_runtime_release_preflight.py` 都是离线工具；它们只读取已经捕获的文件。
- 本地 Pytest fixture、Mock、synthetic demo、`experiment_demo.csv` 以及测试中构造的 `RuntimeCanarySuite` 都不是 release evidence，不能授权 `canary` 或 `default`。
- 真实原始输入、学生数据、Provider 返回、API Key、Flow ID、Authorization 和未脱敏 checkpoint 只能放在受控私有目录；不得提交到仓库或复制到前端/SSE payload。
- `SOLVER_CT v1.0` 及其原始 YAML 不在本流程中修改。没有真实授权成对 trace 和独立语义审查时，保持 Legacy/Runtime release gate fail-closed。

本 runbook 中的 `LEGACY_RESULT.json`、`RUNTIME_RESULT.json`、`RUNTIME_CHECKPOINTS.json`、`CASE_INPUTS.json`、`JUDGEMENTS.json` 和 `RUNTIME_CANARY_SUITE.json` 是操作者在受控目录中准备的文件名占位符，不是仓库中已经存在的生产 artifact。

## 1. 运行前置条件

### 1.1 固定评测身份

在获得授权后，先固定以下值，并在受控评测记录中保存原始来源：

- `agent_id`：实际执行的已发布 Agent ID。
- `agent_version`：该 Agent 的实际版本。
- `runtime_plan_version`：本次 Runtime 计划版本。
- `suite_id`：本次成对套件的唯一 ID。
- `case_id`：每个输入 case 的唯一 ID。
- `authorization_ref`：批准使用这些输入和执行 Provider 的变更/评测记录引用。
- `captured_at`：带时区的采集时间。
- 语义审查使用的 `rubric_version` 和 `reviewer_ref`。

先从只读 readiness 接口确认当前注册、可用性、版本、发布模式和阻塞原因：

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/agents/runtime-readiness |
  ConvertTo-Json -Depth 20
~~~

对于具体 Agent，也可读取：

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/agents/GENERAL_QUESTION_V1 |
  ConvertTo-Json -Depth 20
~~~

只有已发布、能力可用、Runtime 计划和 Provider/Flow 配置完整、且授权记录明确的候选，才可以进入真实执行。readiness 的状态只用于检查，不替代真实执行授权。

#### LearningLoop 当前身份核对

两个 LearningLoop Runtime capability 已在服务和 descriptor 中显式声明
`agent_version=learning-agent-v1`，但计划版本不同：

| capability | Agent version | Runtime plan version | 当前发布结论 |
| --- | --- | --- | --- |
| `TEACHING_INTERACTION_V1` | `learning-agent-v1` | `teaching-interaction-v1` | 尚无 authorized evidence，保持 fail-closed |
| `LEARNING_PROGRESS_V1` | `learning-agent-v1` | `learning-progress-v1` | 尚无 authorized evidence，保持 fail-closed |

`GET /api/v1/learning/runtime-readiness` 返回的版本和 canary 字段只用于核对身份与
阻塞原因；它不把 LearningLoop 变成 `/api/v1/agents/runtime-readiness` 的 Agent
Registry 条目，也不授予真实 Provider、canary 或 default。采集前仍需取得授权并
在 release preflight 中显式传入相同的 expected versions。

### 1.2 运行配置与凭据

真实执行环境必须使用项目既有的 Provider 配置和密钥注入方式。不要把凭据写进命令行、JSON、事件、checkpoint 或本 runbook。发布 gate 相关配置的实际环境变量是：

~~~dotenv
AGENT_RUNTIME_LAUNCH_MODES=
AGENT_RUNTIME_CANARY_ARTIFACTS=
AGENT_RUNTIME_SEMANTIC_EVIDENCE=
AGENT_RUNTIME_RELEASE_GATE_REQUIRED=true
~~~

真实采集阶段只在受控环境按批准的 Agent/模式显式启用；采集完成后再回到 `legacy` 或经批准的 `canary`。不要用通配符或未绑定 Agent 的 artifact 路径。`AGENT_RUNTIME_CANARY_ARTIFACTS` 和 `AGENT_RUNTIME_SEMANTIC_EVIDENCE` 的值在发布配置中采用 `AGENT_ID=PATH` 形式，这是 `RuntimeCanaryReleaseRegistry` 实际解析的格式。

### 1.3 目录隔离

在仓库外建立仅授权人员可读写的评测目录。例如：

~~~powershell
$EvidenceRoot = "<受控私有评测目录>"
New-Item -ItemType Directory -Force $EvidenceRoot | Out-Null
~~~

目录至少分为 `raw/`、`redacted/`、`review/`、`release-record/`。`raw/` 不进入仓库；collector 的输入应来自已经检查过的 `redacted/` 文件。不要用仓库中的 synthetic fixture 代替真实文件来“跑通”本流程。

## 2. 真实执行：Legacy 与 Runtime 必须使用同一输入

采集器没有能力证明两次在线执行使用了同一业务输入；成对关系由操作者在受控记录中建立。因此必须按以下顺序操作：

1. 固定一份规范化输入，并为每个 case 分配 `case_id`。Legacy 和 Runtime 都读取这份输入，不要在两条路径中分别手工重写问题、上下文、附件选择或用户身份。
2. 在授权的隔离环境执行 Legacy，保存脱敏后的 JSON object 到 `LEGACY_RESULT.json`，并保留任务/运行关联信息在私有 release record 中。
3. 对同一个 `case_id`、同一份规范化输入执行 Runtime。Runtime 必须走现有 Task 创建、worker、Provider 和 Task/SSE 边界；路由不得直接在请求线程执行 Provider。
4. 保存 Runtime 的脱敏结果 JSON object 到 `RUNTIME_RESULT.json`，并保存完整的 Runtime checkpoint trace 到 `RUNTIME_CHECKPOINTS.json`。如果 Runtime 等待输入、审批、重规划或失败，不能只保存最终结果，必须保留能解释该生命周期的 trace。
5. 对每个 case 记录采集时间、执行环境、Legacy task ID、Runtime task/run ID、授权引用和输入的私有 hash/索引。它们属于受控操作记录，不是 collector 要求的额外 JSON 字段；不要为了满足脚本而伪造字段。

Runtime checkpoint 应来自持久化的 `agent_checkpoints.state_data`，不要手工重排或修改 `sequence`、`state_version`、`event_sequence`、`AgentRun`、`run_id` 或 plan version。 `collect_runtime_canary.py` 会再次调用 checkpoint audit，并在 trace 不合法时拒绝写出 suite。

## 3. 保存 Task/SSE 证据

Runtime 通过现有 Task/SSE 事件边界输出事件。在线采集期间保存脱敏后的原始 SSE 文本和/或事件 JSON 导出；这些文件由 release record 引用，但不会被三个 collector 自动读取。至少检查：

- 事件 `id`/sequence 单调递增，没有人为补号或删除；
- 断线后使用 `Last-Event-ID` 从上一个 cursor 重连，没有丢失或重复不可接受的事件；
- checkpoint 的 `event_sequence` 与事件导出的顺序能够对应；
- 终态事件、Runtime 失败/等待状态与最终 Task 状态一致；
- SSE payload 只有脱敏摘要和引用 ID，没有原始输入、密钥、Provider 响应或绝对私有路径。

现有读取接口和重连接口是：

~~~powershell
# 读取已持久化事件；after 是上次已保存的 sequence
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/tasks/<TASK_ID>/events?after=<SEQUENCE>" |
  ConvertTo-Json -Depth 20

# 流式读取；重连时将上次收到的 id 放入 Last-Event-ID
curl.exe -N -H "Last-Event-ID: <SEQUENCE>" "http://127.0.0.1:8000/api/v1/tasks/<TASK_ID>/stream"
~~~

若事件顺序或重连检查失败，立即停止证据打包；现有回归入口为 `apps/api/tests/test_sse_event_order.py` 和 `apps/api/tests/test_sse_reconnect.py`。测试通过只能说明协议回归通过，不能代替这次真实执行的 SSE 保存记录。

## 4. 脱敏检查

在文件进入 collector 前逐项检查：

- 删除 API Key、Bearer/Authorization、Cookie、Flow ID、内部 URL、绝对路径和未授权的用户/学生标识；
- 只保留语义审查所需的最小输入、Legacy/Runtime 输出摘要、证据引用和结构状态；
- 不改动用于审计的 checkpoint 顺序和状态版本；如果只能通过修改 trace 才能“通过”，应废弃本次采集并重新执行；
- 将脱敏状态标记为脚本实际要求的 `redaction_status=redacted`，而不是把未知状态当作已脱敏；
- 运行仓库敏感文件扫描：

~~~powershell
python scripts/check_sensitive_files.py
~~~

扫描失败、发现真实凭据或不确定是否已脱敏时，不得继续。原始文件留在受控目录，不复制到公共仓库。

## 5. 结构成对套件：Legacy/Runtime/checkpoint

### 5.1 推荐的多 case manifest

`collect_runtime_canary.py` 支持的 manifest schema 是 `runtime_canary_manifest.v1`。manifest 中实际支持的顶层字段是：

~~~json
{
  "schema_version": "runtime_canary_manifest.v1",
  "agent_id": "<AGENT_ID>",
  "agent_version": "<AGENT_VERSION>",
  "runtime_plan_version": "<RUNTIME_PLAN_VERSION>",
  "suite_id": "<SUITE_ID>",
  "authorization_ref": "<AUTHORIZATION_REF>",
  "captured_at": "<ISO-8601 WITH TIMEZONE>",
  "cases": [
    {
      "case_id": "<CASE_ID>",
      "legacy": "redacted/<CASE_ID>.legacy.json",
      "runtime": "redacted/<CASE_ID>.runtime.json",
      "checkpoints": "redacted/<CASE_ID>.checkpoints.json"
    }
  ]
}
~~~

这里只展示脚本实际接受的字段和相对路径关系，不提供一个可被误认为真实证据的样例值。manifest 引用的文件必须位于 manifest 所在目录之下；脚本会拒绝缺失文件、路径穿越、越界 symlink、未知字段、重复 `case_id` 和非法 checkpoint。manifest 本身不会被复制到输出 suite。

将 manifest 放在受控目录后执行：

~~~powershell
$py = ".\\.venv\\Scripts\\python.exe"
& $py scripts/collect_runtime_canary.py --manifest "$EvidenceRoot\\manifest.json" --output "$EvidenceRoot\\redacted\\RUNTIME_CANARY_SUITE.json"
~~~

collector 成功时会输出结构评测报告，并写出 `RuntimeCanarySuite`。它要求 `authorized_paired`、非空授权引用、Agent/Agent version/Runtime plan version、带时区的 `captured_at` 和 `redaction_status=redacted`，且所有 case 的结构 gate 通过。失败时不应把部分文件手工拼成 suite。

### 5.2 单 case 兼容命令

只有一个 case 时，也可以使用脚本保留的单 case 参数：

~~~powershell
& $py scripts/collect_runtime_canary.py --agent-id "<AGENT_ID>" --agent-version "<AGENT_VERSION>" --runtime-plan-version "<RUNTIME_PLAN_VERSION>" --suite-id "<SUITE_ID>" --case-id "<CASE_ID>" --authorization-ref "<AUTHORIZATION_REF>" --captured-at "<ISO-8601 WITH TIMEZONE>" --legacy "$EvidenceRoot\\redacted\\LEGACY_RESULT.json" --runtime "$EvidenceRoot\\redacted\\RUNTIME_RESULT.json" --checkpoints "$EvidenceRoot\\redacted\\RUNTIME_CHECKPOINTS.json" --output "$EvidenceRoot\\redacted\\RUNTIME_CANARY_SUITE.json"
~~~

需要只查看一个已生成 suite 的离线报告时：

~~~powershell
& $py scripts/evaluate_runtime_canary.py "$EvidenceRoot\\redacted\\RUNTIME_CANARY_SUITE.json" --require-release-eligible
~~~

这里的 `release_eligible` 是结构套件自身的授权/结构 gate 结果，不是语义等价结论；语义 sidecar 仍然必须单独采集并交给 preflight。

## 6. 独立语义审查与 sidecar

### 6.1 审查输入

审查人员在受控目录读取脱敏后的同一输入和两份脱敏输出，逐 case 记录实际支持的 judgement 字段：

- `dimensions`：仅允许 `task_fulfillment`、`factual_correctness`、`evidence_faithfulness`、`safety`，每项为 `0..1` 或 `null`；
- `decision`：`pass`、`needs_review` 或 `fail`；
- `judge_type`：`human`、`model` 或 `hybrid`；
- `rubric_version`、`reviewer_ref`、带时区的 `reviewed_at`；
- `redaction_status`：必须为 `redacted`；
- `authorization_ref`：语义审查授权引用。

`JUDGEMENTS.json` 是以 `case_id` 为键的 JSON object，必须覆盖 suite 中每一个且只覆盖每一个 case。它不是公开数据集，也不应包含原始答案或额外未定义字段。任何 `needs_review`、`fail`、case 缺失、版本不一致或 hash 绑定不一致都不能进入发布。

### 6.2 生成 sidecar

`CASE_INPUTS.json` 同样是以 `case_id` 为键的 JSON object。collector 从输入、Legacy 输出和 Runtime 输出计算 SHA-256；sidecar 不保存原始输入，只保存 hash、审查字段和身份绑定。

~~~powershell
& $py scripts/collect_runtime_semantic_evidence.py --suite "$EvidenceRoot\\redacted\\RUNTIME_CANARY_SUITE.json" --inputs "$EvidenceRoot\\redacted\\CASE_INPUTS.json" --judgements "$EvidenceRoot\\review\\JUDGEMENTS.json" --output "$EvidenceRoot\\redacted\\RUNTIME_SEMANTIC_EVIDENCE.json"
~~~

该命令要求结构 suite 是 `authorized_paired` 且已通过结构 release gate；它会拒绝缺失/多余 case、judgement 未知字段、非 `redacted` 状态、无时区 `reviewed_at` 和非法维度。sidecar 的 Agent、Agent version、Runtime plan version、suite 和 case 必须与结构 suite 绑定。

## 7. Provider-free release preflight

在同一受控 release record 中保存 suite、semantic sidecar、SSE 导出、checkpoint trace、授权引用、版本信息和审查记录。然后运行：

~~~powershell
& $py scripts/check_runtime_release_preflight.py --agent-id "<AGENT_ID>" --suite "$EvidenceRoot\\redacted\\RUNTIME_CANARY_SUITE.json" --semantic-sidecar "$EvidenceRoot\\redacted\\RUNTIME_SEMANTIC_EVIDENCE.json" --expected-agent-version "<AGENT_VERSION>" --expected-runtime-plan-version "<RUNTIME_PLAN_VERSION>" | Tee-Object "$EvidenceRoot\\release-record\\preflight.json"
$preflightExit = $LASTEXITCODE
~~~

该命令不会执行 Provider，只读取并绑定结构 suite 和 semantic sidecar。应检查输出中的实际字段：`provider_free`、`structural_eligible`、`semantic_eligible`、`release_eligible`、`blocking_reasons` 和 `next_steps`。只有 `provider_free=true`、结构和语义均为 eligible、`release_eligible=true`、且没有 blocking reason 时，才允许把结果提交给独立发布审批。

`--expected-agent-version` 和 `--expected-runtime-plan-version` 是本次 release record 的显式身份绑定，不是可选的自描述字段。即使 suite 和 sidecar 内部彼此一致，省略任一参数也必须 fail-closed；preflight 会报告 `release_expected_agent_version_missing` 或 `release_expected_runtime_plan_version_missing`，不能把 artifact 自报版本当作发布目标版本。

以下情况必须视为失败并保持 Legacy：缺 suite、缺 sidecar、`synthetic`/未授权证据、Agent/版本/plan/suite/case 不匹配、checkpoint 非法、语义覆盖不完整、hash 不匹配、`decision` 不是 `pass`、脱敏失败或 preflight 退出码非 0。preflight 成功也不自动改配置、不自动发布。

## 8. canary/default 决策

### 8.1 决策表

| 条件 | 决策 | 配置动作 |
| --- | --- | --- |
| 真实执行前置条件、授权或脱敏不完整 | 拒绝 | 保持 Legacy；不运行 collector 发布流程 |
| 结构 suite 失败 | 拒绝 | 不进入 canary/default；修复后重新采集成对 trace |
| 结构通过但 semantic sidecar 缺失/绑定失败/非 pass | 拒绝 | 保持 Legacy；补充独立语义审查或废弃该 suite |
| preflight 全部通过，但尚未完成独立发布审批 | 仅可作为候选 | 不切换 launch mode |
| preflight 通过且审批同意小流量验证 | canary | 只为明确 Agent 配置 `AGENT_ID=canary` |
| canary 观察期内出现回归、trace/SSE 异常、语义失败或证据过期 | 回滚 | 配置 `AGENT_ID=legacy` |
| canary 观察完成且有新的明确审批 | 才可考虑 default | 将同一 Agent 显式改为 `AGENT_ID=default` |

Runtime 的真实模式名由 `RuntimeLaunchMode` 定义为 `legacy`、`shadow`、`canary`、`default`。发布时必须使用具体 Agent 绑定，例如：

~~~dotenv
AGENT_RUNTIME_LAUNCH_MODES=GENERAL_QUESTION_V1=canary
AGENT_RUNTIME_RELEASE_GATE_REQUIRED=true
AGENT_RUNTIME_CANARY_ARTIFACTS=GENERAL_QUESTION_V1=<受控私有suite路径>
AGENT_RUNTIME_SEMANTIC_EVIDENCE=GENERAL_QUESTION_V1=<受控私有sidecar路径>
~~~

上述配置只展示真实解析格式；`<...>` 必须替换为当前已批准、与版本匹配的受控路径。修改配置后按项目部署流程重启/重新加载服务，再次读取 `/api/v1/agents/runtime-readiness` 确认 configured/effective mode 和 blocker。不能把 preflight 的 `release_eligible=true` 解读为自动 default 授权。

### 8.2 观察与记录

canary 期间每次真实 Runtime 执行都要保存脱敏 Task/SSE 摘要和异常，并与当前 Agent/plan/artifact 版本绑定。观察记录至少回答：是否产生未授权副作用、是否能从 checkpoint 恢复、是否出现重复/丢失 SSE、是否出现结构化结果或证据完整性回归。代码没有替本项目规定统一的流量比例、样本量或质量阈值，因此本 runbook 不虚构数字；阈值必须在授权记录中事先写明并由发布审批人确认。

## 9. 失败回滚

任一以下信号出现即停止扩大流量：preflight 重新失败、artifact 版本漂移、任何成对执行无法形成完整 checkpoint、SSE 顺序/重连异常、Runtime 终态与 Task 不一致、语义 `needs_review`/`fail`、敏感信息泄漏、非幂等副作用或 Provider/Flow 未授权。

回滚步骤：

1. 将对应 Agent 显式切回 Legacy：

   ~~~dotenv
   AGENT_RUNTIME_LAUNCH_MODES=<AGENT_ID>=legacy
   AGENT_RUNTIME_RELEASE_GATE_REQUIRED=true
   ~~~

2. 按项目部署流程重新加载配置；如果没有显式模式，当前策略的默认行为也是 `legacy`，但回滚记录仍应写明显式配置和时间。
3. 读取 `/api/v1/agents/runtime-readiness`，确认该 Agent 的 effective mode 为 Legacy/阻塞，并确认 release gate 仍开启。
4. 用一个不含敏感数据的受控 smoke request 验证 Task 创建仍非阻塞、终态仍由现有 Task/SSE 边界提交；重连时继续使用 `Last-Event-ID`。
5. 保留失败 suite、sidecar、preflight JSON、checkpoint、SSE 导出和授权记录，不覆盖原文件；在 release record 中标记回滚原因。不要通过删除 artifact、关闭 gate 或修改测试来“恢复绿色”。
6. 修复后必须重新建立同输入的 Legacy/Runtime 成对 trace、重新做语义审查、重新运行 preflight，并取得新的审批；旧证据不能跨 Agent version 或 Runtime plan version 复用。

## 10. 完成判定与当前限制

一次采集/发布评测只有在以下条件全部满足时才算完成：

1. 授权、版本、Agent readiness、Provider/Flow 和脱敏前置条件已记录；
2. 每个 case 有同输入的 Legacy 结果、Runtime 结果和完整 checkpoint trace；
3. SSE 顺序、重连、终态和 checkpoint 关联已检查并保存；
4. `collect_runtime_canary.py` 成功生成 `authorized_paired` suite；
5. `collect_runtime_semantic_evidence.py` 成功生成完整 sidecar，所有 release case 的 `decision` 为 `pass`；
6. `check_runtime_release_preflight.py` 返回 0 且 `release_eligible=true`；
7. 独立发布审批明确记录 `canary`、继续 Legacy、回滚或 `default`，以及可执行的回滚配置。

本仓库已有的 `apps/api/tests/test_runtime_evidence_intake_contract.py`、`docs/evaluation/runtime_evidence_intake_contract.md` 和其他 Runtime 测试只能验证离线合同、fail-closed 行为和结构绑定。它们不提供真实 Provider 结果、真实 Legacy/Runtime 成对 trace、真实 SSE 导出或生产发布授权；在这些材料到位前，正确结论仍是“不具备 production canary/default 资格”。

## 11. 相关实现与验证入口

- 采集结构 suite：`scripts/collect_runtime_canary.py`
- 离线结构评测：`scripts/evaluate_runtime_canary.py`
- 生成语义 sidecar：`scripts/collect_runtime_semantic_evidence.py`
- provider-free 发布门禁：`scripts/check_runtime_release_preflight.py`
- Legacy/Runtime 离线差异：`scripts/compare_runtime_legacy.py`
- checkpoint 离线审计：`scripts/audit_runtime_trace.py`
- SSE 顺序/重连回归：`apps/api/tests/test_sse_event_order.py`、`apps/api/tests/test_sse_reconnect.py`
- 当前 evidence intake 合同：`docs/evaluation/runtime_evidence_intake_contract.md`

文档变更本身的最低检查命令：

~~~powershell
git diff --check
python scripts/check_sensitive_files.py
~~~
