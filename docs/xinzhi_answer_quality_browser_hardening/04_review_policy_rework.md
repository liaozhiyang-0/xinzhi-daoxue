# 04 waiting_review 与人工审批策略专项

## 一、当前问题

人工复测发现：

> 很多普通任务经常进入人工审批。

这在技术上可能符合旧流程，但产品体验差。

---

# 二、重新定义审批边界

应该进入 waiting_review 的主要类型：

## A

正式教师评分/发布。

## B

知识库发布、删除、回滚等治理操作。

## C

需要人工确认的不可逆业务动作。

---

# 三、默认不应审批的类型

以下正常情况下不得进入 waiting_review：

```text
普通课程问答
专业解题
电路图片解题
多图题
学生追问
学习解释
普通数据分析
普通科研知识解释
```

---

# 四、教案场景

教案可以：

```text
直接生成草稿
+
标记“建议教师复核”
```

而不是必须停在 waiting_review 才不给正文。

如果确实需要审批：

页面必须先显示完整草稿。

---

# 五、Research

实时证据不足：

优先：

```text
基于已有证据生成受限简报
+
标记证据不足
```

而不是直接停止。

只有涉及正式发布时再审批。

---

# 六、Review Policy 统一化

检查：

```text
AgentDefinition
Scenario
Runtime
Validator
Result Governance
```

是否各自都有 review 判断。

如果存在多处：

应统一到共享 ReviewPolicy。

不要多个 Runtime 各写逻辑。

---

# 七、浏览器实测

至少统计：

```text
100 个普通任务
```

中：

```text
unexpected_waiting_review_rate
```

目标：

```text
接近 0
```

---

# 八、输出

```text
docs/audit/40_review_policy_report.md
```
