# Phase G：真实 Provider Baseline 与 Benchmark Harness

## 一、目标

解决 Phase B-E 最大证据缺口：

> 当前结构验证很多，但真实模型质量证据不足。

Phase G 不进行大规模优化。

只建立可信 baseline。

---

# 二、测试层级

统一：

```text
L0 synthetic_provider_free
L1 offline_real_case
L2 real_provider_test
L3 controlled_canary
L4 production
```

Phase G 至少完成：

- L0
- L1

如果 API key 和预算允许，再完成小规模 L2。

---

# 三、Real Provider Benchmark Harness

需要统一记录：

```text
case_id
course
task_type
input_mode
provider
model
model_version
prompt_version
planner_version
skill_version
rag_version
tool_version
reflection_enabled
experience_enabled
latency
tokens
cost
answer
score
failure_stage
```

---

# 四、建立冻结基线

优先选择：

```text
40-80 representative cases
```

覆盖：

### Academic Solver

- CT
- AE
- DE
- SS
- DSP

### Knowledge

- explanation
- retrieval-grounded QA

### Research

- search
- synthesis

### Teaching

- lesson prep
- assignment review

### Input

- text
- formula
- single image
- multiple image（若当前正式支持）
- PDF/text material

---

# 五、真实 Provider 预算

建议默认：

```text
max_cases = 30
max_retries_per_case = 1
temperature = stable / low
```

必须记录成本。

---

# 六、Baseline Freeze

最终生成：

```text
evaluation/baselines/agentic_v1_real_baseline.json
docs/audits/phase_g_real_provider_baseline.md
```

包含：

- overall
- course
- task
- input mode
- latency
- cost
- failure
- evidence level

---

# 七、禁止

不允许：

- 根据测试结果立即大改 Agent；
- 跑一题改一题；
- 无控制重复调用 Provider；
- 修改评分器提升分数。

Phase G 只建立基线。

---

# 八、提交

整个 Phase G 完成后一次：

```text
git commit -m "feat(eval): complete phase G real-provider baseline"
git push
```

GitHub CI 记录后进入 H。
