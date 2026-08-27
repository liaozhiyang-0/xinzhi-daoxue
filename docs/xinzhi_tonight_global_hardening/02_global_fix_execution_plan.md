# 02 全局性修复执行计划

## 一、修复总原则

每个问题都必须先回答三个问题：

### Q1

这是单场景问题，还是共享框架问题？

### Q2

如果只修当前失败点，是否可能破坏其他 Agent / Runtime / Provider？

### Q3

能否在共享层建立契约、断言或统一策略，防止同类问题再次出现？

---

# 二、修复层级

修复优先顺序：

```text
Contract
↓
State
↓
Capability
↓
Context
↓
Runtime
↓
Provider / Tool
↓
Validation
↓
Presentation
↓
Scenario-specific behavior
```

Scenario-specific patch 必须是最后选择。

---

# 三、推荐的全局增强方向

## 1. 启动时 Capability Health Matrix

在系统启动或 debug API 中生成：

| Agent | Enabled | Runtime | Provider | Tools | Skills | RAG | Multimodal | Ready |
|---|---|---|---|---|---|---|---|---|

发现：

```text
Agent enabled
但 Runtime handler 不存在
```

应启动时就暴露。

不要等用户第一次点击才发现。

---

## 2. Runtime Preflight

Task 真正执行前进行轻量 preflight：

```text
Agent exists
Runtime available
required tools available
required provider available / fallback known
attachments ready
session accessible
```

Preflight 不应把非阻塞任务创建变慢太多。

可以放在 executor 开始阶段。

---

## 3. 统一 Runtime Execution Policy

集中定义：

```text
node timeout
provider timeout
retry
cancel
review
fallback
failure mapping
```

不要每个 Agent Runtime 各写一套。

已知 Knowledge Runtime 超时问题就是这种漂移的典型证据。

---

## 4. Multimodal Manifest

建立统一附件清单。

要求浏览器、API、DB、Runtime、Provider 都保留：

```text
original_index
```

任何排序操作必须显式。

增加：

```text
attachment_count expected == actual
```

断言。

用户指代：

```text
第一张
第二张
最后一张
图A
图B
```

需要有稳定解析逻辑或清晰映射。

---

## 5. Context Priority / Correction Override

建立“最新显式用户纠正最高优先级”规则。

例如：

```text
turn 1: R2=10
turn 6: 我写错了，R2=20
```

Context Assembly 应产生：

```text
R2=20
```

旧值只能作为历史，不得作为当前 working fact。

建议 working state 支持：

```text
fact key
value
source turn
supersedes
```

如现有系统已有工作状态结构，优先扩展现有机制。

---

## 6. Follow-up Continuity Policy

对短追问：

```text
为什么？
继续。
这里呢？
第二种？
```

Router 默认继承：

```text
previous agent
intent
course
scenario context
```

除非当前输入包含明确切换意图。

避免用户每一轮都重新说明题目。

---

## 7. Result Contract Normalizer

所有 Runtime 输出先进入统一 Normalizer：

```text
raw runtime result
→ normalized result
→ semantic validation
→ presentation
```

目的：

- fallback provider 也能返回统一结构；
- 某个 Agent 缺字段时不会直接前端空白；
- warnings / citations / review state 统一。

---

## 8. Failure Taxonomy

统一内部错误：

```text
CAPABILITY_UNAVAILABLE
RUNTIME_TIMEOUT
PROVIDER_TIMEOUT
PROVIDER_INVALID_OUTPUT
ATTACHMENT_MISSING
MULTIMODAL_ORDER_ERROR
CONTEXT_LOST
VALIDATION_FAILED
EXTERNAL_EVIDENCE_UNAVAILABLE
```

对用户映射为自然语言。

日志保留技术细节。

---

## 9. State Transition Guard

实现或增强：

```text
can_transition(old, new)
```

关键状态变化必须经过 guard。

增加回归：

```text
cancelled → completed  forbidden
failed → completed     forbidden
completed → running    forbidden
```

retry 应创建新 lineage，而不是修改旧终态。

---

## 10. Cross-Scenario Regression Harness

建立一个测试 harness：

```text
run_case(case)
```

统一记录：

```text
scenario
intent
agent
runtime
provider
attachments
events
result
semantic grade
latency
```

以后修一个框架模块时，至少跑：

```text
6 场景 smoke
+
受影响能力集
```

避免修改一处、另一处坏掉。

---

# 四、修改影响分析

每次共享层修改前：

必须写：

```text
Affected modules
Affected agents
Affected scenarios
Affected tests
Potential regressions
```

修改后：

```text
Target tests
Cross-scenario smoke
Contract tests
```

全部执行。

---

# 五、禁止“简单补丁”的典型行为

禁止：

```python
if agent_id == "LEARN_01_KNOWLEDGE_QA_V1":
    ...
```

如果真实问题是：

```text
所有 supported_agent_ids 都没进入 launch policy
```

应修 registry / resolver。

禁止：

```python
if len(images) == 2:
```

如果真实问题是附件顺序没有统一 manifest。

禁止：

```javascript
if (scenario === "...") reset intent
```

如果真实问题是 scenario state 生命周期没有统一管理。

禁止：

```python
timeout = 60
```

如果真实问题是 Runtime 没有使用 AgentDefinition.timeout。

---

# 六、修复记录

每项修复记录：

| FIX ID | Gap | Root Cause | Shared Layer | Files | Impact | Regression |
|---|---|---|---|---|---|---|

最终输出：

```text
docs/audit/25_global_fix_report.md
```
