# 01 全局框架漏洞审计任务

## 一、目标

不要从现有报错出发逐个修。

先回答：

> 当前系统有哪些设计缺口，会导致不同 Agent、不同场景、不同输入类型在未来反复出现同类 Bug？

---

# 二、重点审计的 12 个框架层

## 1. Scenario Contract

检查当前所有场景：

- scenario_id
- intent
- course_id
- options
- attachment requirements
- expected agent
- review policy
- expected result contract

是否由多个地方重复定义。

重点搜索：

- HTML `data-*`
- workspace.js 常量
- config/scenario
- Task payload
- backend scenario catalog
- Router mapping

目标：

> 一个场景的核心契约不能由前端、后端、测试各自维护不同版本。

如果当前存在多源定义：

优先形成统一校验，而不是立即大迁移。

至少增加启动/测试时一致性检查。

---

## 2. Task Contract

检查：

```text
Frontend payload
→ Pydantic model
→ DB Task input
→ Runtime request
→ AgentRequest
```

字段是否有：

- 重命名；
- 丢失；
- 默认值漂移；
- null / missing 语义不同；
- list 顺序改变；
- metadata 被删掉。

重点：

```text
scenario_id
intent
course_id
session_id
attachments
options
answer depth
memory flags
use_local_rag
include_images
```

建立 Contract Test。

---

## 3. Agent Capability Contract

曾经已经出现：

> AgentDefinition 存在，但 Runtime allowlist 不认识 `supported_agent_ids`。

这说明当前：

```text
AgentRegistry
Runtime Launch Policy
Provider Handler
Tool Registry
```

之间可能没有统一 Capability Source of Truth。

审计：

```text
agent_id
supported_agent_ids
runtime_type
provider
skills
tools
capabilities
timeout_seconds
review_policy
```

是否被多个模块各自解释。

目标：

> Agent 注册成功后，系统应该能够自动验证其 Runtime、Tool、Skill、Provider 依赖是否全部满足。

建议建立：

```text
AgentCapabilityResolver
```

或等效的集中校验服务。

不要为了名字重构；如果已有类似服务，增强现有实现。

---

## 4. Runtime Policy

检查所有 Runtime：

- timeout 是否来自统一 AgentDefinition；
- retry 是否统一；
- cancel 是否统一；
- provider timeout 与 node timeout 是否存在竞争；
- waiting_user / waiting_review 是否统一；
- failure code 是否统一；
- Task/AgentRun/Node 是否一起收敛。

禁止每个 Runtime 自己写一套超时和异常逻辑。

---

## 5. Capability / Tool / Skill Registry

检查 Tool：

- 是否注册；
- 是否启用；
- Provider 是否可用；
- 当前 Agent 是否允许；
- 输入输出合同；
- timeout；
- fallback。

系统应在任务执行前尽量发现：

```text
TOOL_UNAVAILABLE
PROVIDER_UNAVAILABLE
CAPABILITY_MISMATCH
```

而不是运行到一半才报 `NoneType` 或 handler missing。

---

## 6. Multimodal Orchestration

重点确认系统有没有真正的“多模态编排层”。

不能仅仅：

```text
attachments: list[file]
```

然后全部交给模型。

需要明确：

```text
Attachment
→ type detection
→ order
→ ingestion state
→ image normalization
→ multimodal manifest
→ AgentRequest
→ Provider
```

建议建立统一 `MultimodalInputManifest` 或等效结构。

至少包含：

```text
attachment_id
file_id
original_index
mime_type
role
status
storage_ref
width/height（如可用）
user_reference_name（如“第二张图”）
```

目标：

> 用户说“第二张图”时，Runtime 有稳定的第二张图定义。

---

## 7. Context Assembly

必须明确 Context Priority：

建议检查并形成类似：

```text
Current user turn
> explicit user correction
> current task working state
> current session recent context
> session summary
> relevant long-term memory
> RAG evidence
> generic profile/default
```

避免旧摘要覆盖新条件。

重点测试：

```text
R2=10Ω
→ 用户纠正 R2=20Ω
```

后续绝不能继续使用 10Ω。

---

## 8. Memory Architecture

分开：

```text
Conversation history
Working state
Session summary
Long-term memory
Experience memory
```

不要混为一个“memory”。

明确：

- 写入条件；
- 读取条件；
- 用户关闭 memory 的行为；
- 纠错行为；
- version；
- soft-delete；
- Session isolation。

---

## 9. Router Context

Router 不应只根据当前短文本判断。

例如：

```text
第一轮：复杂电路题
第二轮：为什么？
```

第二轮不能因为没有关键词而转成普通知识问答。

审计 Router 是否使用：

```text
session active intent
previous task agent
current scenario
course
attachments
working state
```

建议形成 follow-up continuity policy。

---

## 10. Semantic Validation

当前 Result Validator 不应只验证：

```text
字段存在
JSON 合法
answer 非空
```

还应根据任务类型支持：

- 数值答案校验；
- 单位；
- 结构完整性；
- citation 真实性；
- 图像引用数量；
- 用户要求服从；
- 相互矛盾检测；
- 关键步骤缺失检测。

不要求一次做完全部智能 Judge。

先形成统一扩展接口。

---

## 11. Task State Machine

系统必须定义允许状态转换。

例如：

```text
created → queued
queued → running
running → completed
running → failed
running → cancelled
running → waiting_user
running → waiting_review
```

检查：

- cancelled 后是否可能 completed；
- retry 是否污染原任务；
- waiting_review 是否被前端当 loading；
- runtime crash 是否留下 running；
- reboot 是否恢复 lease。

建议增加显式状态转换断言。

---

## 12. Presentation Contract

所有 Agent 输出最终都应该进入统一 Presentation Contract。

检查：

```text
answer
structured_result
citations
warnings
review_state
attachments
math_content
evidence
next_action
```

不能某个 Agent 返回完全不同字段导致前端静默失败。

---

# 三、审计输出

生成：

```text
docs/audit/19_global_framework_gap_audit.md
```

至少包括：

| GAP ID | 层 | 当前设计 | 风险 | 已发生证据 | 潜在影响场景 | 修复优先级 | 建议修复层 |
|---|---|---|---|---|---|---|---|

---

# 四、禁止事项

此阶段不修改业务逻辑。

只能：

- 阅读；
- 画调用链；
- 建风险矩阵；
- 标记共享根因；
- 设计测试。

完成审计后再开始修改。
