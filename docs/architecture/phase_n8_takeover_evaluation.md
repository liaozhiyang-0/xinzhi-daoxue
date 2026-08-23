# Phase N8：Presentation 解耦与 Active Takeover 评估

> 评估日期：2026-08-23
> 当前分支：`refactor/platform-modernization`

## 1. 结论

Phase N8 的目标是把展示层从固定 Agent ID 解耦，并验证 Planner 接管后仍保留 Phase M 的用户可见契约。当前展示层继续消费 `TaskPresentation`、`TaskExecutionSummary`、`EvidenceViewItem` 和 `scenario_contract`，不根据 Agent ID 创建专属页面。

生产任务的目标控制链为：

```text
React / chat / tasks
  → UnifiedRequestPreparationService
  → GoalContract
  → TaskRouter deterministic preflight
  → PlannerService(active)
  → CapabilityBindingRegistry + SkillRegistry/Policy
  → CanonicalPlan
  → RuntimeTaskEngine / PlanExecutor
  → business Runtime / tool / RAG / model
  → verification / governance / review
  → TaskResultPresentationService
  → SSE / React
```

`TaskRouter` 只提供输入、可用性和粗粒度候选信息；它不再拥有最终业务计划。`scenario_catalog` 只提供案例提示、约束、证据策略和 presentation metadata，不决定生产 workflow。

## 2. 展示解耦检查

| 检查项 | 当前证据 | 结果 |
| --- | --- | --- |
| 六个 showcase 仍有稳定业务语义 | `apps/web/src/demo/scenarios.ts`、`config/scenarios.yaml` | PASS |
| AC-01 图片入口可复现 | `/demo-assets/case6-opamp.png`、文件上传测试 | PASS |
| 结果页使用统一结构化展示 | `TaskResultPresentationService` → `build_task_views` | PASS |
| 数学渲染仍只有 Markdown/KaTeX 链 | `apps/web` math fixtures | PASS（31 条基线） |
| `waiting_review` / `waiting_user` 仍是状态，不被结果页改写 | Runtime control 与 UI contract tests | PASS |
| 新 capability 不要求新 Agent 页面 | presentation profile + generic fallback | PASS |
| 内部 Agent ID 不作为学生展示字段 | task presentation / workspace contract | PASS |

## 3. 六案例 Controlled Planner 证据

命令：

```powershell
.\.venv\Scripts\python.exe scripts\validate_planner_controlled_takeover.py
```

结果：

```yaml
valid: true
mode: controlled
case_count: 6
invalid_capabilities: 0
unregistered_skills: 0
route_mutations_after_plan: 0
network_calls: 0
provider_calls: 0
```

覆盖 TP-01、FE-01、LP-01、RB-01、KG-01、AC-01。AC-01 的 goal input modalities 同时包含 `text` 与 `image`；TP-01、FE-01、LP-01、RB-01、KG-01 的 `manual_review_required` 保持为 `true`。

## 4. Active 与兼容路径边界

| 路径 | active 生产任务 | 兼容/测试用途 |
| --- | --- | --- |
| OverallRoutingService | 不注入 Runtime preparation | 仅 shadow 配置可启用 |
| FallbackRoutingService | 不参与 active Planner 接管 | shadow/旧客户端兼容 |
| IntentPlanCompiler | 不生成 active 默认计划 | shadow 与旧 checkpoint adapter |
| `legacy-runtime:*` | active 缺少 CanonicalPlan 时 fail closed | 旧 checkpoint 读取与显式 shadow 兼容 |
| `scenario_catalog` | 提供 metadata/hints/evidence policy | 不拥有最终 Agent/workflow |
| 固定 Agent 页面 | 不存在 | 不新增 |

这一区分避免把“兼容代码仍可被旧测试调用”误报为“active 生产路径仍由旧控制面拥有”。最终退休门槛同时依赖运行时 telemetry 和静态 importer 审计。

## 5. 回归证据

已执行的定向回归包括：

```text
154 passed, 1 skipped
```

覆盖 Planner authoritative/controlled、Runtime preparation/execution、Task/Runtime contracts、SSE/event sequence、六案例矩阵、统一 Web UI、认证、附件导入和 AC-01 图片路由。案例 6 专项检查另为 `18 passed`，frontend demo contract 为 PASS。

全量 pytest、Ruff、Mypy、前端 typecheck/build 和 Git/CI 结果以 Phase N closeout 为准；本文件不把定向回归扩大解释为全量 PASS。

## 6. N8 结论

```text
Presentation parity: PASS
Controlled six-case takeover: PASS
Route mutation after plan: 0
Unregistered capability/skill: 0
AC-01 image contract: PASS
```
