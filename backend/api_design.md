# 第一版 API 设计

## 通用约定

| 项目 | 约定 |
| --- | --- |
| 基础路径 | `/api/v1` |
| 请求格式 | `application/json` |
| 返回格式 | 统一包含 `code`、`message`、`data`、`trace_id` |
| 时间格式 | ISO 8601 字符串，如 `2026-06-24T10:00:00+08:00` |
| 身份上下文 | 第一版可使用请求中的 `user_id`，后续接入正式登录鉴权 |
| 错误处理 | 参数错误返回 `400`，未授权返回 `401`，资源不存在返回 `404`，Agent 调用失败返回 `502` |

## 通用返回结构

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "trace_id": "req-20260624-000001"
}
```

## 1. 学生智能问答接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/qa` |
| 请求方式 | POST |
| 说明 | 调用课程问答 Agent，保存问答记录并返回结构化答案。 |

### 请求参数

```json
{
  "user_id": "10001",
  "course_id": "1",
  "course_name": "模拟电子技术",
  "knowledge_point_id": "AE-001",
  "question": "MOS 管饱和区的判断条件是什么？",
  "answer_style": "formula",
  "history_limit": 5
}
```

### 返回参数

```json
{
  "record_id": "90001",
  "answer": "以增强型 NMOS 为例，饱和区需要满足 VGS > Vth 且 VDS >= VGS - Vth。",
  "knowledge_points": [{"id": "AE-001", "name": "MOS 管工作区"}],
  "key_points": ["先判断导通", "再判断 VDS 条件"],
  "formula_or_rules": ["VGS > Vth", "VDS >= VGS - Vth"],
  "analysis_steps": ["判断 VGS 是否超过阈值", "计算 VGS - Vth", "比较 VDS"],
  "common_mistakes": ["只判断 VGS > Vth"],
  "recommended_review": ["复习 MOS 管工作区判断表"],
  "confidence": "high",
  "need_more_information": false
}
```

## 2. 错题诊断接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/wrong-question/diagnose` |
| 请求方式 | POST |
| 说明 | 调用错题诊断 Agent，保存错题记录并更新学习画像。 |

### 请求参数

```json
{
  "user_id": "10001",
  "course_id": "1",
  "knowledge_point_id": "AE-001",
  "question_text": "判断 NMOS 是否工作在饱和区。",
  "student_answer": "VGS 大于 Vth，所以饱和。",
  "reference_answer": "需同时满足 VGS > Vth 且 VDS >= VGS - Vth。"
}
```

### 返回参数

```json
{
  "wrong_record_id": "80001",
  "diagnosis_summary": "该答案遗漏了 VDS 判断条件。",
  "is_correct": false,
  "error_types": [
    {
      "code": "condition_missing",
      "name": "判断条件遗漏",
      "evidence": "学生只写出 VGS > Vth"
    }
  ],
  "related_knowledge_points": [{"id": "AE-001", "name": "MOS 管工作区"}],
  "missing_steps": ["未比较 VDS 与 VGS - Vth"],
  "correct_solution_outline": ["先判断导通", "再判断饱和区条件", "给出工作区结论"],
  "student_friendly_explanation": "VGS > Vth 只能说明 MOS 管导通，不能直接说明处于饱和区。",
  "review_suggestions": ["完成 3 道 MOS 工作区判断题"],
  "priority": "high"
}
```

## 3. 学习建议接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/study-suggestion` |
| 请求方式 | POST |
| 说明 | 聚合问答、错题和学习画像，调用学习规划 Agent 生成建议。 |

### 请求参数

```json
{
  "user_id": "10001",
  "course_id": "1",
  "learning_goal": "期末复习",
  "available_days": 7,
  "daily_minutes": 45
}
```

### 返回参数

```json
{
  "overall_assessment": "近期薄弱点集中在 MOS 工作区和时序约束。",
  "priority_knowledge_points": [
    {
      "id": "AE-001",
      "name": "MOS 管工作区",
      "priority": 1,
      "reason": "错题中多次遗漏判断条件"
    }
  ],
  "study_plan": [
    {
      "day": 1,
      "theme": "MOS 管工作区判断",
      "tasks": ["整理条件表", "完成 3 道判断题", "复盘错题"],
      "expected_output": "能独立判断截止区、线性区和饱和区",
      "estimated_minutes": 45
    }
  ],
  "practice_suggestions": ["先练条件判断题，再练综合电路题"],
  "mastery_checks": ["随机给定 VGS、VDS、Vth 后能在 1 分钟内判断工作区"],
  "risk_reminders": ["若条件判断不熟，会影响放大电路静态工作点分析"]
}
```

## 4. 教师端高频问题统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/high-frequency-questions` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date`、`limit` |
| 说明 | 返回指定范围内学生高频问题 Top N。 |

### 返回参数

```json
{
  "items": [
    {
      "question_summary": "MOS 管饱和区如何判断？",
      "knowledge_point_id": "AE-001",
      "knowledge_point_name": "MOS 管工作区",
      "count": 18,
      "last_asked_at": "2026-06-24T10:00:00+08:00"
    }
  ]
}
```

## 5. 教师端错题类型统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/error-types` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date` |
| 说明 | 返回错题类型分布，用于饼图或柱状图展示。 |

### 返回参数

```json
{
  "items": [
    {"error_type": "condition_missing", "error_type_name": "判断条件遗漏", "count": 12, "ratio": 0.32}
  ]
}
```

## 6. 教师端薄弱知识点统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/weak-knowledge-points` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date`、`limit` |
| 说明 | 综合错题次数、问答次数和学习画像，返回薄弱知识点排名。 |

### 返回参数

```json
{
  "items": [
    {
      "knowledge_point_id": "DE-004",
      "knowledge_point_name": "建立时间与保持时间",
      "wrong_count": 15,
      "qa_count": 22,
      "score": 86.5
    }
  ]
}
```

## 7. 学生活跃度统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/activity` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date` |
| 说明 | 返回问答次数、错题提交次数和活跃学生数趋势。 |

### 返回参数

```json
{
  "items": [
    {
      "date": "2026-06-24",
      "qa_count": 45,
      "wrong_submit_count": 20,
      "active_student_count": 18
    }
  ]
}
```

## 8. 教师教学建议生成接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/teaching-suggestion` |
| 请求方式 | POST |
| 说明 | 聚合教师端统计数据，调用教师分析 Agent 生成教学建议。 |

### 请求参数

```json
{
  "course_id": "1",
  "class_id": "class-01",
  "start_date": "2026-06-01",
  "end_date": "2026-06-24"
}
```

### 返回参数

```json
{
  "class_summary": "班级问题集中在 MOS 工作区和 D 触发器时序图。",
  "top_risks": ["判断条件遗漏", "时钟边沿判断错误"],
  "teaching_suggestions": ["安排一次条件判断专题讲解", "增加时序图边沿采样练习"],
  "recommended_exercises": ["MOS 工作区判断题", "D 触发器波形题"],
  "follow_up_metrics": ["相关错题率", "高频问题数量变化"]
}
```

## 第一版实现顺序建议

1. 先实现学生智能问答接口，打通课程问答 Agent。
2. 实现错题诊断接口，并写入 `wrong_record`。
3. 基于 `qa_record` 和 `wrong_record` 实现学习建议接口。
4. 使用聚合 SQL 实现教师端三个统计接口。
5. 最后接入教师分析 Agent 生成教学建议。
