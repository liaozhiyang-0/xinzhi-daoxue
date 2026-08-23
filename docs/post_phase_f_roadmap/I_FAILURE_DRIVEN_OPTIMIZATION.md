# Phase I：Failure-driven Targeted Optimization

## 一、目标

真正开始优化。

所有优化必须来自 Phase H Top Failure Patterns。

禁止：

> “感觉这里可能可以改。”

---

# 二、选择优化目标

只选择：

```text
Top 5-8 Failure Patterns
```

优先级：

```text
severity × frequency × user impact
```

例如：

- 图片结构识别
- 数学公式解析
- 复杂推导遗漏
- Skill 选择错误
- RAG evidence mismatch
- Reflection false positive
- 长回答质量下降
- fallback 不合理

---

# 三、每个 Pattern 独立 Proposal

形式：

```text
Pattern
↓
Root Cause Evidence
↓
Minimal Proposal
↓
Targeted Test
↓
Replay
↓
Regression
```

---

# 四、允许优化层

可以修改：

### Planner

只有 route/plan 证据支持时。

### Skill

- metadata
- trigger
- prerequisite
- binding

### RAG

- query rewrite
- filter
- rerank
- evidence threshold

### Tool

- deterministic calculation
- parsing
- formatting

### Academic Solver

- domain procedure
- prompt
- verification

### Reflection

- trigger
- critic criteria

### Experience

- retrieval filtering
- conflict handling

---

# 五、优化轮次

Phase I 最多：

```text
3 rounds
```

### Round 1

Top 3-5 最高价值问题。

### Round 2

只处理 Round 1 仍失败问题。

### Round 3

收口，不再扩大范围。

---

# 六、每轮门禁

必须：

```text
target cases improve
critical regression = 0
global degradation acceptable
latency/cost acceptable
```

失败则 rollback candidate。

---

# 七、禁止

- 为每题写特例；
- keyword patch 爆炸；
- 新建 Agent；
- 重写 Runtime；
- 用更贵模型掩盖架构问题；
- 修改测试答案迎合模型；
- 无限优化。

---

# 八、输出

```text
docs/audits/phase_i_targeted_optimization.md
evaluation/reports/phase_i/
```

必须列：

```text
before
after
score delta
failure delta
latency delta
cost delta
regressions
```

---

# 九、提交

整个 Phase I 一次：

```text
git commit -m "feat(agent): complete phase I targeted optimization"
git push
```
