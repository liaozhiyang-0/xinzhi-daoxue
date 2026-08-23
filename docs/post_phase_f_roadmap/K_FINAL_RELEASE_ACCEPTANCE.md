# Phase K：Final Acceptance / Release Candidate

## 一、目标

形成：

```text
芯智导学 Agentic v1.0 Release Candidate
```

这个阶段不再新增核心功能。

只：

- 修 critical bug
- 固定版本
- 验证
- 打包
- 文档化

---

# 二、最终 Benchmark

运行：

### 必须

- 336-case full
- Phase H expanded benchmark
- Phase I targeted regression
- Phase J robustness suite

### 可选

小规模 real-provider representative set。

---

# 三、最终指标

至少：

```text
overall score
course score
hard-case score
image score
knowledge grounding
research evidence
teaching quality
critical error rate
latency p50/p95
cost
fallback rate
runtime failure rate
```

---

# 四、版本冻结

冻结：

```text
planner_version
skill_registry_version
prompt_version
rag_index_version
tool_version
reflection_version
experience_version
evaluation_version
```

---

# 五、Release Gate

必须：

```text
critical regression = 0
public API compatible
DB migration valid
CI status known
no secret
no untracked required file
benchmark reproducible
rollback documented
```

---

# 六、答辩/展示准备

输出：

```text
docs/release/
```

建议包括：

- architecture overview
- evaluation methodology
- benchmark results
- before/after optimization
- failure-driven loop
- safety/governance
- demo scenarios
- known limitations

---

# 七、Demo Cases

固定：

```text
8-12
```

不能只选最简单题。

建议：

- 复杂电路
- 图片题
- 知识问答
- 信号系统题
- 教学场景
- Research
- fallback
- Reflection 修正案例

---

# 八、Known Limitations

必须公开：

- 多图能力边界
- 真实 Provider 覆盖规模
- Experience conditional evidence
- 某些专业课程题库规模
- 成本/延迟限制

---

# 九、Tag

完成后：

```text
git commit -m "release: complete phase K release candidate"
git push
```

如用户明确允许：

```text
tag v1.0.0-rc1
```

不要自动 merge main 或自动 release production。

---

# 十、最终产物

```text
Agentic v1.0 RC
Benchmark Report
Failure Analysis Report
Optimization Report
Robustness Report
Architecture Report
Demo Cases
Known Limitations
```
