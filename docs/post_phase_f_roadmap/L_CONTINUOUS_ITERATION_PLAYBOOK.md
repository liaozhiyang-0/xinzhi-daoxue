# Phase K 之后：长期 Iteration Playbook

## 核心原则

Phase K 之后不再建新 Phase 架构。

采用固定迭代周期。

---

# 每轮 Iteration

```text
New Cases / User Feedback
        ↓
Benchmark
        ↓
Failure Pattern
        ↓
Top 3 Problems
        ↓
Improvement Proposal
        ↓
Offline Replay
        ↓
Full Regression
        ↓
Release
```

---

# 建议节奏

每次只优化：

```text
3-5 个高价值问题
```

不要一次修改整个系统。

---

# 每轮必须回答

1. 哪些 case 失败？
2. failure stage 是什么？
3. 是否可复现？
4. 根因 evidence 是什么？
5. 修改了哪一层？
6. target case 是否改善？
7. 全局有没有退化？
8. latency/cost 是否变差？
9. 是否值得发布？

---

# 测试集增长

建议：

```text
336
→ 500
→ 800
→ 1000+
```

但重点不是数字。

重点是覆盖：

- 课程
- 难度
- 图像
- 公式
- 真实学生问题
- 边界情况
- 故障情况

---

# 测试集划分

长期建议：

```text
development
regression
hidden holdout
real-world
```

不要所有题都用于调优。

---

# 防止过拟合

至少保留：

```text
20-30%
```

hidden holdout。

Codex 日常修改不能看到完整期望答案或针对这些 case 写规则。

---

# Release 节奏

例如：

```text
v1.0
v1.1
v1.2
```

每次 release 附：

```text
benchmark delta
top fixes
regressions
known limitations
```

---

# 最终长期状态

项目开发范式应稳定为：

> 不再扩 Agent 数量，而是持续提高已有 Planner + Skill + Runtime + Evaluation 的真实任务质量。
