# Codex 总执行指令：浏览器真实体验与回答质量专项

读取并严格执行本目录全部文件，以本文件为总纲。

当前阶段不再以：

```text
任务跑通
API 200
pytest passed
```

作为主要成功标准。

用户人工复测已经明确发现：

1. 回答质量差；
2. 解题经常直接降级；
3. 经常不给最终答案；
4. 普通问题也频繁 waiting_review；
5. 同一个问题不能稳定给出相同核心答案；
6. 后端测试通过但浏览器真实体验仍有问题。

因此本阶段最高目标是：

> **浏览器里真实用户能稳定拿到完整、直接、有用的答案。**

---

## 最高要求 1：Browser First

所有重要问题必须先在：

```text
http://127.0.0.1:8000/workspace
```

真实复现。

修复后必须再次浏览器验证。

禁止仅后端测试后宣布修复。

如已有浏览器自动化，优先复用。

否则建立轻量 browser E2E。

---

## 最高要求 2：正常可解问题必须尽量回答

对：

```text
solve_problem
knowledge question
student follow-up
image problem
multi-image problem
general academic question
```

只要整体可理解：

> 默认必须尽量给出最终答案。

不能因为轻微：

```text
RAG不足
图片局部模糊
证据不足
tool失败
provider fallback
```

直接不给答案。

---

## 最高要求 3：重构 Degrade Policy

将降级统一为：

```text
L0 normal
L1 soft degrade
L2 partial degrade
L3 hard stop
```

L1/L2 仍应给出尽可能完整答案。

只有真正无法继续才 L3。

---

## 最高要求 4：重构 Review Policy

普通学生任务原则上不进入 waiting_review。

waiting_review 主要保留给：

```text
正式评分
正式发布
知识治理
不可逆操作
```

教案和科研可直接给草稿，并标记“建议复核”，不要无正文卡在审批。

---

## 最高要求 5：同题稳定性

选取真实问题：

```text
至少20题 × 5次
```

从浏览器重复提交。

记录：

```text
agent
provider
review state
degrade level
final answer
semantic grade
```

排查 Router、Provider、RAG、Validator、Review、Timeout 等漂移。

---

## 最高要求 6：真实题优先

优先使用本地已有：

```text
电路题
电路图
题目截图
多图题
已有 benchmark
人工复测失败题
```

不要用大量过于简单的 mock 代替真实问题。

---

## Phase 1

先建立：

```text
docs/audit/37_browser_acceptance_baseline.md
```

记录浏览器当前真实失败模式。

先不要急着修改。

---

## Phase 2

建立：

```text
Answer Quality Contract
Degrade Policy
Review Policy
```

明确哪些问题必须直接回答。

---

## Phase 3

浏览器执行真实测试矩阵。

重点捕捉：

```text
无答案
不合理降级
不合理审批
同题漂移
前端结果缺失
多图漏图
追问丢上下文
```

---

## Phase 4

按共享根因修复：

```text
PROMPT_POLICY
ROUTER
PROVIDER
RAG
DEGRADE_POLICY
REVIEW_POLICY
SEMANTIC_VALIDATOR
RESULT_NORMALIZER
PRESENTATION
MULTIMODAL
CONTEXT
```

禁止只改提示文案掩盖后端问题。

---

## Phase 5

修复后必须同时跑：

```text
target backend tests
+
browser reproduction
+
browser cross-scenario smoke
```

---

## Phase 6

重新执行同题稳定性测试。

目标：

```text
core answer consistency >= 95%
```

数值标准题尽量：

```text
>= 98%
```

---

## Phase 7

完成最终浏览器验收。

最终不能只返回：

```text
backend tests passed
```

必须实际给出：

```text
browser task count
unexpected waiting_review
hard degrade
semantic grade
same-question stability
multi-image behavior
```

---

## Phase 8

完成 Git commit。

推荐：

```text
fix: improve answer quality and browser interaction reliability
```

---

# 最终目标

本阶段不是做到：

> “系统不报错”。

而是做到：

> **普通用户在浏览器里问一个正常问题时，大多数情况下能一次得到完整答案，不会莫名其妙被降级、卡审批或得到空洞回复；同一个问题重复问，核心结论也应基本稳定。**
