# 教师分析 Agent

## Agent 目标

帮助教师理解班级学习情况，基于高频问题、错题类型、薄弱知识点和活跃度统计生成教学建议。

## 输入

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| course_id | string | 课程标识 |
| class_id | string | 班级标识 |
| high_frequency_questions | array | 高频问题统计 |
| error_type_stats | array | 错题类型统计 |
| weak_point_stats | array | 薄弱知识点统计 |
| activity_stats | object | 学生活跃度统计 |

## 处理流程

1. 分析班级高频问题和薄弱知识点。
2. 识别共性错误类型和教学风险。
3. 结合课程进度生成教学建议。
4. 输出课堂讲解、作业布置和复习安排建议。

## 调用资源

- 教师端统计数据。
- 课程知识点目录。
- 错题类型分布。
- 历史教学建议记录。

## 输出格式

```json
{
  "class_summary": "班级学情摘要",
  "top_risks": ["主要风险"],
  "teaching_suggestions": ["教学建议"],
  "recommended_exercises": ["建议补充题型"],
  "follow_up_metrics": ["后续观察指标"]
}
```

## Prompt 初稿

```text
你是电子信息课程教师分析助手。请根据班级统计数据生成教学建议。建议应服务于教师备课、课堂讲解、作业讲评和后续跟踪，避免空泛表述。
```

## 与自研系统的接口关系

自研后端通过教师端统计接口生成基础指标，再通过 `/api/v1/teacher/teaching-suggestion` 调用 Agent 生成教学建议文本，供教师端看板展示。
