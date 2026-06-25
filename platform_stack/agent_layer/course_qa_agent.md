# 课程问答 Agent 设计

## 1. 新定位

课程问答 Agent 不再承担复杂题图解题任务，主要负责课程概念解释、公式适用条件、章节检索、简单纠错和学习建议。

它保留原有课程问答能力，并将“错题诊断”降级为内部的简易纠错模块。当学生问“我这一步为什么错了”“这个公式能不能用”时，课程问答 Agent 可以结合 `wrong_reason_tags.md` 给出错因提示，但不强制输出完整错题诊断报告。

## 2. 主要功能

- 概念解释；
- 公式适用条件说明；
- 解题步骤提示；
- 简单错误提醒；
- 推荐复习章节；
- 关联知识点检索。

## 3. 与识图解题 Agent 的分工

| 场景 | 推荐 Agent |
|---|---|
| 用户上传题图或电路图 | 识图解题 Agent |
| 用户问概念、公式、为什么 | 课程问答 Agent |
| 用户追问某一步 | 根据上下文由课程问答 Agent 或识图解题 Agent 继续解释 |
| 用户只给文字题干且无图 | 课程问答 Agent，可在条件不足时要求补图 |
| 用户问“我这一步哪里错” | 课程问答 Agent 简易纠错模块 |

## 4. 输入

| 字段 | 说明 |
|---|---|
| `course_id` | 课程标识，例如 `01_circuit_theory`。 |
| `question` | 学生原始问题。 |
| `chapter_hint` | 可选章节范围。 |
| `history` | 最近对话摘要。 |
| `student_step` | 可选，学生给出的某一步推导。 |

## 5. 输出

```json
{
  "answer": "直接回答",
  "concepts": ["相关概念"],
  "formula_conditions": ["公式适用条件"],
  "step_hint": ["下一步提示"],
  "simple_error_hint": {
    "has_error": true,
    "possible_reason_tag": "time_constant_error",
    "explanation": "时间常数中的 R 应从储能元件端口看入。"
  },
  "recommended_review": ["推荐复习章节"],
  "need_image_solver": false,
  "need_more_information": false
}
```

## 6. 简易纠错边界

课程问答 Agent 可以做：

- 判断某个公式是否适用；
- 指出一步推导的常见错误；
- 给出 1-3 个可能错因标签；
- 推荐章节和练习方向。

课程问答 Agent 不负责：

- 从复杂图片中还原电路；
- 输出完整错题诊断报告；
- 替代识图解题 Agent 完成多节点图像推理；
- 在缺少题图时猜测电路结构。

## 7. 调用资源

- `course_materials/`：章节知识库；
- `questions/question_type_index.md`：题型索引；
- `wrong_cases/wrong_reason_tags.md`：错因标签；
- `wrong_cases/diagnosis_rules.md`：简易纠错规则参考；
- `evaluation/circuit_question_design_guide.md`：结构化电路题设计参考。

