# 芯智导学 Phase F 之后总路线：从架构收口进入大规模实测与迭代

## 一、总体结论

Phase F 完成后，不再新增新的 Agent 控制层，也不继续设计 G/H/I 式“架构层”。

后续阶段全部属于：

> 真实验证 → 大规模实测 → 失败驱动优化 → 稳定性与压力测试 → 最终发布验收

建议继续执行 5 个大阶段：

```text
Phase F
Evaluation Loop 收口
        ↓
Phase G
真实 Provider 基线与测试基础设施冻结
        ↓
Phase H
大规模 Benchmark Campaign
        ↓
Phase I
Failure-driven Targeted Optimization
        ↓
Phase J
Robustness / Stress / Regression
        ↓
Phase K
Final Acceptance / Release Candidate
        ↓
长期 Iteration Loop
```

Phase G-K 不再新增新的控制面，只允许针对已有：

- Planner
- Skill
- RAG
- Tool
- Academic Solver
- Reflection
- Experience
- Runtime
- Evaluation

做数据驱动的最小必要修改。

---

## 二、为什么 Phase F 后还需要 5 个阶段

### Phase G：真实 Provider 基线

Phase B-E 大量结果仍属于：

- synthetic_provider_free
- structural validation
- conditional go

因此必须先建立真实模型条件下的基线。

### Phase H：大规模实测

336-case 应从“测试集”升级为：

- 全量 Benchmark
- failure attribution source
- regression baseline

并进一步扩充真实题、图片题、复杂公式题和跨课程题。

### Phase I：定向优化

不能再凭感觉改 Agent。

以后所有优化必须：

```text
Failure Pattern
→ Proposal
→ Minimal Change
→ Replay
→ Full Regression
```

### Phase J：鲁棒性与压力

正确率高不代表系统可用。

还必须测试：

- 并发
- 长上下文
- 多附件
- 图片
- Provider timeout
- RAG 不可用
- Tool failure
- resume/retry
- fallback
- latency/cost

### Phase K：最终验收

形成真正可答辩、可展示、可部署的 Release Candidate。

---

# 三、统一 Git 规则

从 Phase G 开始：

> 一个大阶段只提交一次。

例如：

```text
Phase G 全部完成
→ local validation
→ git commit
→ git push
→ GitHub Actions
```

不再对子任务分别提交。

建议分支：

```text
agentic/phase-g-real-baseline
agentic/phase-h-large-benchmark
agentic/phase-i-targeted-optimization
agentic/phase-j-robustness
agentic/phase-k-release-candidate
```

阶段完成提交建议：

```text
feat(eval): complete phase G real-provider baseline
test(eval): complete phase H large-scale benchmark
feat(agent): complete phase I targeted optimization
test(system): complete phase J robustness validation
release: complete phase K release candidate
```

---

# 四、无人值守执行原则

Codex 可以连续执行 G→H→I→J→K，但必须服从硬门禁。

## 允许自动继续

如果：

- 当前阶段 targeted tests PASS；
- 没有 critical regression；
- 没有破坏 public contract；
- 没有超出 Provider 预算；
- 没有 destructive git operation；

则可以自动进入下一阶段。

## 必须停止

遇到以下任意情况必须停止：

1. 数据库 migration 无法安全回滚；
2. public API 需要破坏性修改；
3. critical correctness regression；
4. 大量测试突然下降；
5. 需要真实付费 API 且没有明确预算；
6. secret / token 不存在；
7. Git 分支或工作树存在无法判断归属的冲突修改；
8. 需要 force push / reset --hard；
9. 需要自动 merge main；
10. 需要自动开启 production/canary。

---

# 五、真实 Provider 成本门禁

默认：

```text
Real Provider Test = controlled
```

必须设置：

- max_cases
- max_model_calls
- max_tokens
- max_estimated_cost
- timeout

没有预算配置时：

> 跳过真实 Provider 测试，继续 provider-free / offline-real 测试，并将结果标记为 CONDITIONAL。

禁止：

- 无上限跑全量 336 case 的付费模型；
- 自动更换更贵模型；
- 为追求成绩重复多次调用同一题。

---

# 六、最终目标

Phase K 完成后，项目应从：

> “Agent 架构比较完整”

升级为：

> “有真实 Benchmark、有失败归因、有定向优化证据、有鲁棒性数据、有可复现 Release Candidate 的电子信息课程群垂类 Agent 系统”。

此后不再进入新的架构 Phase。

进入固定循环：

```text
Benchmark
→ Failure Pattern
→ Targeted Improvement
→ Replay
→ Regression
→ Release
```
