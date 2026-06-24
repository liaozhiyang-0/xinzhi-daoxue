# 错题诊断 Agent

## Agent 目标

根据学生提交的题目、学生答案、参考答案和知识点信息，诊断错误原因，给出修正思路和针对性复习建议。

## 输入

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_id | string | 学生标识 |
| course_id | string | 课程标识 |
| question_text | string | 题目内容 |
| student_answer | string | 学生答案 |
| reference_answer | string | 参考答案 |
| knowledge_point_id | string | 可选知识点标识 |

## 处理流程

1. 对比学生答案与参考答案。
2. 识别知识点、公式、步骤和结论差异。
3. 归类错误类型。
4. 给出修正后的解题步骤。
5. 生成个性化复习建议。

## 调用资源

- 错题样例库。
- 课程知识点资料。
- 题库参考答案。
- 学生历史错题记录。

## 输出格式

```json
{
  "diagnosis_summary": "错误诊断摘要",
  "error_types": ["判断条件遗漏", "概念混淆"],
  "missing_steps": ["缺失的关键步骤"],
  "correct_solution_outline": ["步骤1", "步骤2"],
  "review_suggestions": ["复习建议"],
  "related_knowledge_points": ["AE-001"]
}
```

## Prompt 初稿

```text
你是电子信息课程错题诊断助手。请根据题目、学生答案和参考答案诊断错误原因。输出必须结构化，重点说明错误类型、缺失步骤、正确思路和复习建议。不要只给最终答案，要帮助学生理解为什么错。
```

## 与自研系统的接口关系

自研后端通过 `/api/v1/student/wrong-question/diagnose` 接收错题数据，调用 Agent 后保存 `wrong_record`，并更新学生学习画像中的薄弱知识点。
