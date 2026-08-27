# 05 同题稳定性专项

## 一、核心问题

同一个问题目前可能：

```text
Run 1 有答案
Run 2 降级
Run 3 waiting_review
Run 4 结果不同
```

这是用户最容易感知的不稳定。

---

# 二、测试方式

选取至少：

```text
20 个真实问题
```

其中：

```text
文字题 8
单图题 5
多图题 4
自由问答 3
```

每题：

```text
重复 5 次
```

共至少：

```text
100 次浏览器真实提交
```

---

# 三、记录

每次记录：

```text
intent
agent
provider
runtime
RAG
review_state
degrade_level
final_answer
semantic_grade
latency
```

---

# 四、稳定性指标

## Route Stability

同题 Agent 一致率。

## Completion Stability

同题正常回答率。

## Review Stability

不得随机进入 waiting_review。

## Semantic Stability

核心结论一致率。

## Numerical Stability

数值题最终答案一致。

---

# 五、允许变化

允许：

```text
措辞
例子
解释顺序
```

不要求完全 deterministic。

---

# 六、不允许变化

不允许：

```text
最终数值不同
一次有答案一次无答案
一次直接答一次要审批
一次识别成 CT 一次识别成通用
```

---

# 七、排查共享根因

重点检查：

```text
temperature
sampling
provider selection
fallback
RAG top-k
router score threshold
review threshold
timeout
retry
context
image preprocessing
```

---

# 八、目标

普通题：

```text
core_answer_consistency >= 95%
```

数值标准题：

```text
final_numeric_consistency >= 98%
```

---

# 九、输出

```text
docs/audit/41_same_question_stability_report.md
```
