# Agent、Router、Planner 与能力绑定发现

## 观察到的契约分叉

在简单 `explain_concept` tasks 任务中，事件和 task detail 同时出现：

- route：`LEARN_01_KNOWLEDGE_QA_V1`，route confidence 1.0；
- Planner selected capability：`knowledge.govern`；
- knowledge.execute 节点：实际完成；
- result validation：`insufficient`，任务失败。

这不是单纯的模型输出不好，而是路由 Agent、Planner capability、运行节点和结果契约没有形成一条稳定的目标链。该任务对用户来说只是一个基础概念问答，不应落入治理能力并最终被验证器阻断。

## readiness 观察

9 个 readiness 场景均 `production_ready=false`。多数状态是 `configured_unavailable`，知识治理是 `fallback_only`。`runtime_available=true` 只说明部分运行组件存在，不能等价于 Agent 可公开服务。

`/api/v1/models/health` 的 Provider `available=true` 与 `live=false` 同时存在，且公开 chat 实测失败；健康字段语义需要明确区分“配置/网络可达”“模型探活成功”“该路由可执行”。

## 可能根因（未确认）

- scenario catalog、overall routing、Planner 和 capability registry 使用不同粒度的 ID，且存在兼容映射；
- 结果契约验证在知识治理/普通问答之间复用，但 success criteria 不相容；
- fallback 只在 Agent unavailable 时触发，未覆盖“执行成功但结果不足”的情况；
- `POST /api/v1/chat` 仍走兼容/旧执行面，未完全复用 tasks 的 canonical plan。

## 建议的定位顺序

先对同一 request 记录 route fingerprint、planner plan fingerprint、capability binding fingerprint 和 output contract version，断言它们一致；再为基础问答建立最小成功契约和低相关拒答契约；最后才调模型 Prompt。不要先把验证器放宽来掩盖目标错配。
