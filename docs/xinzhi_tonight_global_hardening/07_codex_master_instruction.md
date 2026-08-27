# 07 给 Codex 的今晚总指令

你现在负责 `xinzhi-daoxue` 的一次**全局可靠性框架加固**。

这不是继续进行单点 Bug patch，也不是新功能开发。

当前基线已经证明六个业务场景的标准 Happy Path 可以稳定进入预期 Agent，并且修复后 30 次真实任务中没有系统级 failed。

但是当前仍没有充分证明：

- 高难题；
- 怪题；
- 多图；
- 长对话；
- 用户纠错；
- Session 隔离；
- Context compaction；
- Router follow-up continuity；
- fallback provider 一致性；
- Cancel / Retry / Restart；
- Semantic correctness；
- 回答风格和用户意图服从。

因此今晚目标是：

> **从共享框架漏洞出发完善系统，让用户在非标准使用方式下也尽量不需要操心系统内部状态。**

---

## 最高规则

### 1. 不要打补丁式修复

如果一个问题可能影响多个 Agent / Scenario：

必须定位共享层。

例如：

- AgentDefinition 与 Runtime 不一致 → 修 Capability/Launch Contract；
- 多图遗漏 → 修 Multimodal Manifest / attachment pipeline；
- 短追问丢 Agent → 修 Router continuity/context；
- 用户纠正无效 → 修 Context priority/working state；
- fallback 输出前端坏掉 → 修 Result Normalizer；
- timeout 漂移 → 修 Runtime policy。

禁止为单个 Agent 堆特殊条件。

---

### 2. 修改共享层必须做影响分析

修改前列出：

```text
Affected agents
Affected scenarios
Affected APIs
Affected state
Affected tests
Regression risk
```

修改后必须跑跨场景回归。

---

### 3. 先审计再改

第一步阅读本任务目录：

```text
README.md
01_framework_gap_audit.md
02_global_fix_execution_plan.md
03_extended_real_world_scenarios.md
04_multimodal_memory_intelligence_hardening.md
05_regression_quality_gates.md
06_git_commit_closeout.md
```

然后先生成：

```text
docs/audit/19_global_framework_gap_audit.md
```

在没有明确框架缺口和修复优先级之前，不要开始大范围修改。

---

## 第一阶段：框架一致性

重点检查：

```text
Scenario Contract
Task Contract
Agent Capability
Runtime Policy
Tool/Skill Registry
Multimodal
Context
Memory
Router
Semantic Validator
Task State Machine
Presentation
```

优先找“一个缺口会影响很多功能”的问题。

---

## 第二阶段：建立测试

使用 `03_extended_real_world_scenarios.md`。

至少完成：

```text
难题 / 怪题
多模态
多轮
纠错
Session
故障
Research
RAG
```

覆盖。

不要只检查 `task.status`。

必须增加：

```text
semantic correctness
instruction following
context continuity
user effort
```

---

## 第三阶段：共享修复

按优先级：

```text
Contract
→ State
→ Capability
→ Context
→ Multimodal
→ Runtime
→ Provider
→ Validation
→ UX
```

每次修复：

```text
Root Cause
→ Shared Fix
→ Target Regression
→ Cross Scenario Regression
```

---

## 第四阶段：重点能力

### 多模态

确保：

```text
2~5 图
不丢
不乱序
用户指代正确
部分失败可解释
Provider 不支持多图时不静默截断
```

### 多轮

确保：

```text
短追问继承原任务
最新纠正覆盖旧条件
10~30 turns 不明显失忆
Session 绝不串
memory off 有效
compaction 不覆盖新事实
```

### 智能性

确保用户要求：

```text
只提示
不要答案
简短
详细
换方法
继续我的步骤
只分析第二张图
```

真正改变回答策略。

---

## 第五阶段：Task / Runtime 稳定性

必须测试：

```text
Cancel
Retry
SSE reconnect
polling race
refresh
session switch
dual tab
restart
provider timeout
invalid result
empty result
```

终态必须始终可解释。

---

## 第六阶段：Semantic Validation

不能只验证 JSON。

至少为可自动判定问题增加：

```text
expected numeric result
symbolic/key point checks
unit checks
citation checks
```

如果已有 evaluation framework：

优先复用。

不要重新造巨大评测系统。

---

## 第七阶段：最终回归

执行 `05_regression_quality_gates.md`。

所有核心共享修复都必须有：

```text
unit / contract test
+
real E2E
```

---

## 最终输出

生成：

```text
docs/audit/19_global_framework_gap_audit.md
docs/audit/20_multimodal_framework_report.md
docs/audit/21_context_memory_framework_report.md
docs/audit/22_router_runtime_consistency_report.md
docs/audit/23_semantic_intelligence_report.md
docs/audit/24_fault_state_recovery_report.md
docs/audit/25_global_fix_report.md
docs/audit/26_global_regression_report.md
docs/audit/27_user_resilient_stable_baseline.md
```

---

## 最后必须提交

修复和测试完成后：

```text
git diff --check
tests
E2E
git status
```

确认无异常后提交。

建议：

```text
fix: harden global runtime context and multimodal reliability
```

如果改动适合拆分，可以按框架 / 测试 / 文档分 commit。

不要自动 push，除非当前项目流程已有明确要求。

最终必须向用户返回：

```text
commit hash
commit message
tests
E2E count
major framework fixes
remaining risks
working tree status
```

---

## 成功标准

今晚不是做到：

> “又修好了几个案例”。

而是做到：

> **系统的共享框架更不容易产生同类 Bug，并且以后新增 Agent、场景、多模态能力或 Provider 时，不需要重复踩相同的问题。**

最终目标：

```text
User-Resilient Stable Baseline
```
