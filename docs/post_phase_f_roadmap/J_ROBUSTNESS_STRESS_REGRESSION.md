# Phase J：Robustness / Stress / Regression

## 一、目标

验证：

> 系统不仅会答题，而且在异常环境下不会乱。

---

# 二、输入鲁棒性

测试：

- 空输入
- 信息不足
- 超长输入
- 中文/英文混合
- 公式密集
- PDF
- 单图
- 模糊图片
- 多附件
- unsupported file

---

# 三、Provider 故障

模拟：

```text
timeout
429
500
invalid response
schema violation
slow response
provider unavailable
```

检查：

- fallback
- retry
- budget
- terminal state
- user-visible degradation

---

# 四、RAG 故障

模拟：

- empty retrieval
- low confidence
- wrong course
- embedding unavailable
- reranker unavailable
- index unavailable

要求：

```text
fail-safe
not hallucinate strong evidence
```

---

# 五、Tool 故障

模拟：

- calculation error
- timeout
- malformed output
- dependency unavailable

不能：

```text
quietly fabricate tool result
```

---

# 六、Runtime

重点：

- resume
- retry
- cancel
- checkpoint
- duplicate request
- task worker restart
- interrupted execution

---

# 七、并发与负载

如果环境允许：

```text
1
5
10
20
```

并发逐级测试。

记录：

```text
p50
p95
p99
failure rate
queue delay
memory
CPU
```

不要做无上限压力测试。

---

# 八、长时间稳定性

运行 provider-free / mock：

```text
30-60 min
```

观察：

- memory leak
- dead task
- queue growth
- stale lock
- resource leak

---

# 九、Regression Matrix

必须重新运行：

- Phase H benchmark
- Phase I targeted cases
- Planner tests
- Skill tests
- Reflection tests
- Experience tests
- Runtime tests
- SSE/API contract

---

# 十、输出

```text
docs/audits/phase_j_robustness.md
evaluation/reports/phase_j/
```

---

# 十一、提交

整个 Phase J 一次：

```text
git commit -m "test(system): complete phase J robustness validation"
git push
```
