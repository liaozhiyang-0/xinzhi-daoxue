# 08 最终浏览器回归与 Git 提交

## 一、最终验收必须在浏览器

最后一轮不得只跑 Pytest。

必须打开：

```text
http://127.0.0.1:8000/workspace
```

---

# 二、最终浏览器矩阵

至少：

## 普通文字题

```text
10
```

## 高难题

```text
10
```

## 单图

```text
8
```

## 多图

```text
8
```

## 多轮

```text
5 sessions
```

## 自由问答

```text
10
```

## 同题重复

至少：

```text
10 questions × 3 repeats
```

---

# 三、硬门槛

```text
unexpected_waiting_review = 0 或极低且有合理解释
empty/fake completion = 0
hard_degrade_on_solvable_problem = 0
browser_infinite_loading = 0
same-question core contradiction = 0
silent image drop = 0
latest correction ignored = 0
```

---

# 四、质量门槛

普通题：

```text
A+B >= 95%
```

困难题：

```text
A+B >= 90%
```

同题核心答案一致：

```text
>= 95%
```

---

# 五、后端回归

同时运行：

- Router
- Runtime
- Result Governance
- Review Policy
- Degrade Policy
- Multimodal
- Context/Memory
- Contract
- Six scenarios

---

# 六、代码质量

运行：

```text
Ruff
Mypy 可运行范围
compileall
Node syntax
git diff --check
```

---

# 七、Git commit

关键回归通过后提交。

推荐：

```text
fix: improve answer quality and browser interaction reliability
```

如拆分：

```text
fix: refine degradation and review policies
fix: stabilize solver answer generation
test: add browser-first answer quality regression
docs: close out browser quality hardening
```

---

# 八、最终输出

生成：

```text
docs/audit/37_browser_acceptance_baseline.md
docs/audit/38_answer_quality_report.md
docs/audit/39_degradation_policy_report.md
docs/audit/40_review_policy_report.md
docs/audit/41_same_question_stability_report.md
docs/audit/42_browser_real_world_matrix.md
docs/audit/43_answer_quality_fix_report.md
docs/audit/44_browser_final_acceptance.md
docs/audit/45_answer_quality_stable_baseline.md
```

最终向用户返回：

```text
commit hash
commit message
browser task count
backend test result
unexpected waiting_review rate
hard degrade rate
same-question stability
semantic quality
multi-image result
remaining risks
working tree status
```
