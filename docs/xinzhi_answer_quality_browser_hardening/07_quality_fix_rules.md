# 07 回答质量修复规则

## 一、禁止只修输出文案

如果问题是：

```text
Validator 过度拒绝
Review Policy 错误
Router 漂移
```

不能只改前端提示词。

---

# 二、禁止只放宽所有 Validator

不能为了让系统“都回答”而把校验全部关闭。

应区分：

```text
正确性校验
vs
过度保守阻断
```

---

# 三、共享层优先

问题分类：

```text
PROMPT_POLICY
ROUTER
PROVIDER
RAG
DEGRADE_POLICY
REVIEW_POLICY
SEMANTIC_VALIDATOR
RESULT_NORMALIZER
PRESENTATION
MULTIMODAL
CONTEXT
```

找到共享根因。

---

# 四、修改前

必须列：

```text
Affected agents
Affected scenarios
Affected browser flows
Possible regressions
```

---

# 五、修改后

必须：

```text
Backend targeted tests
+
Browser reproduction case
+
Browser cross-scenario smoke
```

三者全部做。

---

# 六、禁止为了稳定性完全固定模型

可以合理降低随机性，

但不能靠 hardcode answer。

---

# 七、不要为了避免审批直接删除所有 review

Review 对治理/正式评分仍有意义。

只应收紧适用边界。

---

# 八、输出

```text
docs/audit/43_answer_quality_fix_report.md
```
