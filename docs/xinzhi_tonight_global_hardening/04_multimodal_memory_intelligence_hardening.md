# 04 多模态、记忆与回答智能性加固

# 一、多模态框架目标

## 1. 附件必须有统一身份

禁止只靠数组位置。

每个附件至少应能追踪：

```text
file_id
original_index
display_name
mime_type
ingestion_status
```

如果用户称：

```text
图1 / 第一张 / 第二张
```

系统必须能够稳定映射。

---

## 2. 多图完整性校验

Task 开始前：

```text
expected_attachment_count
actual_ready_attachment_count
```

不一致时：

- 能继续则说明缺失；
- 不能继续则明确失败；
- 绝不能无声遗漏。

---

## 3. 多图 Provider 能力检测

如果当前 Provider 只支持单图：

不能 silently 截取第一张。

必须：

- 使用多图 provider；
- 或分图理解 + 结果融合；
- 或明确能力限制。

优先复用当前多模态组件，不要另造一套平行系统。

---

## 4. 多图融合

需要测试：

```text
图1题干
图2电路
图3学生答案
```

模型必须知道各图角色不同。

可以通过 manifest role 或 prompt context 表达。

不要让模型自己猜附件角色。

---

# 二、Memory / Context 目标

## 1. Current Turn First

当前用户明确输入始终优先。

## 2. Correction Override

最新明确纠正优先于旧消息、summary、memory。

## 3. Working State

复杂题建议维护：

```text
known conditions
derived facts
current method
current subproblem
user preference
```

避免每轮从全历史重新猜。

## 4. Session Isolation

任何跨 Session 读取都必须经过明确 long-term memory 规则。

## 5. Memory Off

关闭长期记忆：

- 不写；
- 不跨 Session 读；
- 当前 Session history 仍正常。

## 6. Compaction

压缩前后必须保留：

```text
latest corrected values
current goal
current method
unresolved question
important attachment references
```

---

# 三、回答智能性

## 1. Instruction Following

优先识别：

```text
只提示
不要答案
简短
详细
换方法
只看第二张图
继续我的步骤
```

这些不应被 scenario 默认模板覆盖。

---

## 2. 避免模板化

六个场景输出不能每次固定成完全同样结构。

结构可以统一，但内容策略必须根据问题变化。

---

## 3. 不重复

用户追问局部问题时：

只回答局部。

除非为了完整性必须引用前文。

---

## 4. 错误前提处理

不能顺着明显错误事实继续。

应：

```text
指出错误
解释原因
再继续
```

---

## 5. 不确定性

图片模糊、条件不足、RAG 证据弱时：

使用可理解的不确定性表达。

禁止装作确定。

---

## 6. 用户纠错

用户说：

```text
你这里错了
```

系统应重新检查。

如果用户对：

- 明确承认并修正。

如果用户错：

- 解释证据。

不要因为“上一轮是自己生成的”而偏向维护旧答案。

---

# 四、语义质量检查

专业题最低检查：

```text
final answer
units
sign
formula consistency
major reasoning steps
```

多模态额外检查：

```text
all referenced images considered
image index correct
uncertain values marked
```

科研额外检查：

```text
source existence
title / author / year consistency
DOI / URL validity structure
claim-evidence relation
```

学习路径额外检查：

```text
no fabricated mastery
evidence basis
measurable next step
retest
```

教师场景额外检查：

```text
scope
student level
review point
assessment
```
