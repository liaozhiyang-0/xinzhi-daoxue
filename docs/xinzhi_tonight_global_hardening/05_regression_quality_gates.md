# 05 全局回归与质量门禁

# 一、每次框架修改后的最小回归

任何以下共享模块修改：

```text
Router
Context
Memory
Runtime
Task State
Provider
Multimodal
Result Validator
Presentation
```

都必须运行：

## A. 六场景 smoke

每个至少 1 次真实任务。

## B. 对应定向 Pytest

## C. Contract tests

## D. 至少 3 个边界场景

## E. git diff --check

不得只跑当前失败用例。

---

# 二、今晚最终回归

## 1. 六场景

每场景 3 次：

```text
18 tasks
```

## 2. 难题 / 怪题

至少：

```text
20
```

## 3. 多模态

至少：

```text
20
```

其中：

```text
2图 >= 6
3图 >= 6
4+图 >= 4
异常图片 >= 4
```

## 4. 多轮

至少：

```text
10 sessions
```

每组：

```text
8~15 turns
```

## 5. 状态 / 故障

至少：

```text
10 cases
```

总量目标：

```text
约 80~120 个真实任务
```

如果运行成本过高：

优先保留覆盖，而不是机械追求数字。

---

# 三、硬门槛

## 系统

```text
P0 = 0
核心 P1 = 0
```

## 状态

```text
completed-without-result = 0
infinite-loading = 0
terminal status invisible = 0
```

## Session

```text
cross-session leakage = 0
```

## Correction

```text
new explicit correction ignored = 0
```

## Multimodal

```text
silent image drop = 0
image reorder = 0
```

## Research

```text
fake DOI = 0
fake source = 0
```

## Cancellation

```text
cancelled → completed = 0
```

## Retry

```text
duplicate user message = 0
duplicate final answer = 0
```

---

# 四、质量指标

## Semantic Grade

```text
A = 正确且满足要求
B = 核心正确，存在轻微缺陷
C = 有明显缺失但仍有价值
D = 错误 / 不可靠
```

目标：

普通题：

```text
A+B >= 95%
```

高难题：

```text
A+B >= 90%
```

---

# 五、User Effort Score

```text
0 = 用户一次输入即可得到可用结果
1 = 系统合理要求一次补充 / 审批
2 = 用户需要纠正系统
3 = 系统基本不可用
```

目标：

普通任务大多数：

```text
0
```

不要为了减少 User Effort 而胡乱猜条件。

---

# 六、延迟观察

记录：

```text
p50
p90
p95
max
```

分别统计：

```text
text
rag
single image
multi image
research
```

任何明显长尾必须有原因。

---

# 七、资源稳定性

至少观察：

```text
30 text
10 image
10 multi-image
```

记录进程内存。

如果明显单调增长：

判定 P1/P2 资源问题并排查。

---

# 八、最终报告

生成：

```text
docs/audit/26_global_regression_report.md
docs/audit/27_user_resilient_stable_baseline.md
```

最终报告必须明确：

- 已解决哪些框架漏洞；
- 哪些问题是共享修复；
- 哪些仍是能力边界；
- 哪些外部依赖不可控；
- 多图是否真正可靠；
- 多轮是否真正可靠；
- 用户纠错是否可靠；
- 当前最可能让普通用户困惑的 5 个问题；
- 是否达到“用户用着省心”。
