# 学习规划 Agent

## Agent 目标

结合学生近期问答、错题、薄弱知识点和课程进度，生成可执行的阶段性学习建议。

## 输入

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_id | string | 学生标识 |
| course_id | string | 课程标识 |
| weak_points | array | 薄弱知识点列表 |
| wrong_records | array | 错题摘要 |
| qa_history | array | 问答摘要 |
| available_days | integer | 可选复习周期 |

## 处理流程

1. 汇总学生薄弱知识点和错误类型。
2. 按先修关系和难度排序。
3. 生成短期复习目标。
4. 推荐资料、题型和练习节奏。
5. 输出可跟踪的学习计划。

## 调用资源

- 学习画像。
- 错题记录。
- 问答记录。
- 知识点目录和课程资料。

## 输出格式

```json
{
  "overall_assessment": "学习状态概述",
  "priority_knowledge_points": ["优先复习知识点"],
  "study_plan": [
    {"day": 1, "task": "复习 MOS 管工作区", "expected_output": "完成 3 道判断题"}
  ],
  "practice_suggestions": ["练习建议"],
  "risk_reminders": ["风险提醒"]
}
```

## Prompt 初稿

```text
你是电子信息课程学习规划助手。请根据学生错题、问答历史和薄弱知识点生成阶段性学习建议。建议应具体、可执行、可跟踪，并说明优先级原因。
```

## 与自研系统的接口关系

自研后端通过 `/api/v1/student/study-suggestion` 聚合学习画像和历史记录，调用 Agent 生成建议，并将结果返回学生端学习建议区。
