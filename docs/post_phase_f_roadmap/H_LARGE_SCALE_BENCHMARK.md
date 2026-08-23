# Phase H：大规模 Benchmark Campaign

## 一、目标

将现有 336-case 测试升级为系统级 Benchmark Campaign。

Phase H 不以“全部通过”为目标。

核心目标：

> 真实知道系统到底哪里不好。

---

# 二、第一层：336-case Full Benchmark

完整运行此前 336 cases。

每题记录：

```text
route
planner
skill
rag
tool
generation
reflection
verification
latency
score
failure_stage
failure_codes
```

输出：

```text
overall
per-course
per-task
per-problem-type
per-input-mode
per-agent-capability
```

---

# 三、第二层：扩充测试集

如果已有题库资源允许，扩展到：

```text
500-800 cases
```

不要求一次到 1000。

优先补当前弱项：

### 电路与专业求解

- 综合电路
- 相量
- 暂态
- 三相
- 复杂推导

### 模电/数电

- 电路图
- 工作点
- 放大电路
- 逻辑分析
- 时序电路

### 信号

- convolution
- Fourier
- Laplace
- Z-transform
- sampling

### DSP

- DFT/FFT
- filter
- spectrum
- sampling

### 图片

- 清晰图
- 模糊图
- 多公式
- 图中文字
- 电路连接复杂

---

# 四、难度分级

每题：

```text
easy
medium
hard
expert
```

统计：

```text
accuracy vs difficulty
latency vs difficulty
cost vs difficulty
```

---

# 五、失败聚类

输出 Top Failure Patterns。

至少：

```text
Top 20
```

例如：

```text
P01 image_structure_parse
P02 incomplete_conditions
P03 formula_render
P04 phasor_sign_error
P05 retrieval_mismatch
P06 long_reasoning_degradation
...
```

每个 pattern：

```text
case_count
failure_rate
severity
course
examples
owner
likely cause
```

---

# 六、模型对比

如果预算允许，在小 subset 上比较：

```text
current default
vs
backup model
vs
high-capability model
```

不是全量多模型跑。

推荐：

```text
20-40 representative hard cases
```

---

# 七、输出

```text
docs/audits/phase_h_large_benchmark.md
evaluation/reports/phase_h/
```

核心结论：

```text
Top Failure Patterns
Top Cost Bottlenecks
Top Latency Bottlenecks
Top Course Weaknesses
Top Input Weaknesses
```

---

# 八、禁止

Phase H 不做大规模代码修改。

只允许：

- 修测试框架
- 修 fixture
- 修确定是 benchmark bug 的问题

---

# 九、提交

整个 Phase H 一次：

```text
git commit -m "test(eval): complete phase H large-scale benchmark"
git push
```

完成后进入 Phase I。
