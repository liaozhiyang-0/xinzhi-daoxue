# 03 降级策略专项重构

## 一、已发现问题

当前系统存在：

> 流程能跑通，但为了谨慎频繁降级，导致用户拿不到真正答案。

这说明：

```text
Degrade Policy
```

可能过度保守。

---

# 二、目标

从：

```text
有不确定性
→ 拒绝/降级/审核
```

改为：

```text
有不确定性
→ 尽最大努力作答
→ 明确不确定边界
```

---

# 三、降级等级

建议统一为：

## L0 正常

完整回答。

## L1 Soft Degrade

有轻微不确定性。

仍完整回答，并标记：

```text
基于当前信息...
```

## L2 Partial Degrade

部分输入不可用。

给出：

```text
可确认部分
+
假设
+
参数化或部分答案
```

## L3 Hard Stop

只有：

```text
输入完全不可理解
核心附件全部缺失
明确权限禁止
```

才允许真正停止。

---

# 四、禁止错误升级

以下不应直接 Hard Stop：

```text
RAG hit=0
图片某个标注模糊
外部检索失败
一个 tool timeout
Provider fallback
缺少非核心信息
```

---

# 五、普通解题

对于：

```text
solve_problem
```

默认策略：

> 只要题目整体可理解，就必须尝试给出答案。

不能因为：

```text
evidence insufficient
```

就停止。

专业解题本来就可以依赖模型基础能力。

---

# 六、RAG

RAG 对 Solver 应主要作为：

```text
method support
course grounding
```

不能变成：

```text
无 RAG
→ 无答案
```

---

# 七、图片题

某个参数看不清：

优先：

```text
设该参数为 R
```

继续推导。

---

# 八、工具失败

如果某 Tool 失败：

检查有没有：

```text
model-only fallback
```

不要整个任务失败。

---

# 九、输出

生成：

```text
docs/audit/39_degradation_policy_report.md
```
