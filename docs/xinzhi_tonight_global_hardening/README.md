# 芯智导学：今晚全局可靠性加固目标包

## 目标定位

今晚不是继续做“单点补丁式修 Bug”，也不是继续增加新功能，而是完成一次：

> **从框架漏洞、共享能力缺口、状态一致性、多模态编排、多轮记忆、结果验证和故障恢复出发的全局可靠性加固。**

当前已知基线：

- 六个面板业务场景已经完成标准 E2E 修复。
- 30 次修复后真实任务中：
  - `completed=22`
  - `waiting_review=8`
  - `failed=0`
  - `missing_agent=0`
- 六个场景均能进入预期 Agent。
- 已修复过：
  - 场景 wiring 丢失；
  - Runtime allowlist 未覆盖 `supported_agent_ids`；
  - Knowledge Runtime 超时；
  - 普通文本错误启用图片能力；
  - 资料卡片 / KaTeX 渲染问题。

这些结果只能证明：

> **标准场景 Happy Path 已稳定。**

今晚必须继续证明：

> **真实用户在复杂、多图、多轮、纠错、模糊输入、错误输入、切换会话、依赖失败和高难题下，系统仍然可靠。**

---

# 今晚必须完成的五个主目标

## G1. 从“修 Bug”升级为“修框架缺口”

禁止遇到一个失败就在某个 Agent、某个页面或某个 Runtime 中增加专用 `if/else`。

每个高频问题必须先判断它属于哪一层：

1. `Scenario Contract`
2. `Task Contract`
3. `Context Assembly`
4. `Router`
5. `Agent Registry`
6. `Capability / Tool Registry`
7. `Runtime Policy`
8. `Multimodal Orchestration`
9. `Memory`
10. `Retrieval`
11. `Provider`
12. `Semantic Validation`
13. `Task State Machine`
14. `SSE / Polling`
15. `Presentation / UX`

如果多个场景共享同一根因：

> 必须修共享层，而不是分别补丁。

---

## G2. 建立全局契约和一致性检查

今晚要重点排查：

- Scenario 定义和前端 data-* 是否一致；
- Task payload 与后端 schema 是否一致；
- AgentRegistry 与 Runtime launch policy 是否一致；
- Agent 定义的 timeout、capabilities、supported_agent_ids 是否真正被 Runtime 使用；
- Tool / Skill / Provider 的 enable 状态是否有统一来源；
- 多图附件顺序是否从浏览器一直保持到 Provider；
- Session / Memory / Context 的优先级是否明确；
- Task 状态机是否存在“完成但无结果”“取消后完成”等非法状态；
- fallback provider 是否遵守同一 Result Contract；
- Validator 是否跨所有 Agent 共用一致的错误和结果结构。

---

## G3. 加固三条最重要的用户链路

### A. 多模态

目标：

> **多图不漏图、不乱序、不误指代，图像能力按需启用，失败可降级。**

### B. 多轮对话与记忆

目标：

> **用户不需要不断重复条件；新条件覆盖旧条件；Session 不串；短追问不丢路由；长会话压缩后仍保留关键约束。**

### C. 回答智能性

目标：

> **系统不仅“能回答”，而且能理解用户真正想要的回答方式。**

例如：

- “只告诉我哪里错了”
- “不要完整答案”
- “换一种方法”
- “继续我刚才的步骤”
- “只解释第二张图”
- “刚才 R2 写错了”
- “不要再重复前面的推导”
- “用更直观的方式解释”
- “我只想核对最终结果”

---

## G4. 扩充真实问答与边界场景

不能继续只测六张示例卡片。

今晚需要建立更接近真实学生/教师使用习惯的测试集，覆盖：

- 标准问答；
- 高难题；
- 怪题；
- 缺条件；
- 矛盾条件；
- 错误前提；
- 口语；
- 错别字；
- 多图；
- 多轮；
- 用户纠错；
- 回答风格切换；
- Session 切换；
- RAG 空结果；
- 外部 provider 失败；
- 任务取消；
- 刷新恢复；
- 并发；
- 长上下文。

---

## G5. 修复完成后提交

今晚不是只生成报告。

最终必须：

1. 完成代码修复；
2. 完成关键回归；
3. 形成收口文档；
4. `git diff --check`；
5. 运行约定测试；
6. 确认工作区无意外文件；
7. commit。

建议最终提交信息：

```text
fix: harden global runtime context and multimodal reliability
```

如果改动较多，可拆成：

```text
fix: harden shared runtime and capability contracts
fix: stabilize multimodal context and memory flows
test: expand adversarial and interaction regression coverage
docs: close out global reliability hardening
```

不要自动 push，除非仓库当前流程明确要求并且用户已有该约定。

---

# 今晚执行顺序

严格按照：

```text
Phase 0  基线冻结
Phase 1  全局框架漏洞审计
Phase 2  契约与状态一致性检查
Phase 3  多模态框架加固
Phase 4  多轮上下文与记忆加固
Phase 5  Router / Runtime / Provider / Validator 全局一致性
Phase 6  问答智能性与用户体验
Phase 7  极端场景测试
Phase 8  共享根因修复
Phase 9  全局回归
Phase 10 Git 提交与收口
```

不要跳过前两步直接改代码。

---

# 今晚停止条件

只有满足以下条件才允许收口：

- P0 = 0；
- 核心 P1 = 0；
- 六场景基础 smoke 仍通过；
- 多图附件遗漏 = 0；
- 多图顺序错误 = 0；
- Session 串线 = 0；
- 用户纠正后仍使用旧参数 = 0；
- completed-without-result = 0；
- cancelled-after-completed / completed-after-cancelled = 0；
- infinite-loading = 0；
- 假 DOI / 假引用 = 0；
- 短追问不再频繁丢失原 Agent；
- fallback provider 不破坏结果合同；
- 至少一轮高难题、怪题、多图、多轮和故障注入回归完成；
- 所有共享修复有对应回归测试；
- 完成 Git commit。

最终目标：

> **建立一个“用户乱用也不容易坏”的 User-Resilient Stable Baseline。**
