# 第一版 API 设计

## 通用约定

- 基础路径：`/api/v1`
- 请求格式：`application/json`
- 返回格式：统一包含 `code`、`message`、`data`。
- 用户身份：第一版可使用占位 `user_id`，后续接入正式鉴权。

## 1. 学生智能问答接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/qa` |
| 请求方式 | POST |
| 请求参数 | `user_id`、`course_id`、`knowledge_point_id`、`question`、`history_limit` |
| 返回参数 | `answer`、`key_points`、`formula_or_rules`、`common_mistakes`、`recommended_review`、`record_id` |
| 说明 | 调用课程问答 Agent，保存问答记录并返回结构化答案。 |

## 2. 错题诊断接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/wrong-question/diagnose` |
| 请求方式 | POST |
| 请求参数 | `user_id`、`course_id`、`knowledge_point_id`、`question_text`、`student_answer`、`reference_answer` |
| 返回参数 | `diagnosis_summary`、`error_types`、`missing_steps`、`correct_solution_outline`、`review_suggestions`、`wrong_record_id` |
| 说明 | 调用错题诊断 Agent，保存错题记录并更新学习画像。 |

## 3. 学习建议接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/study-suggestion` |
| 请求方式 | POST |
| 请求参数 | `user_id`、`course_id`、`available_days` |
| 返回参数 | `overall_assessment`、`priority_knowledge_points`、`study_plan`、`practice_suggestions`、`risk_reminders` |
| 说明 | 聚合问答、错题和学习画像，调用学习规划 Agent 生成建议。 |

## 4. 教师端高频问题统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/high-frequency-questions` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date`、`limit` |
| 返回参数 | `items[{question_summary, knowledge_point_id, count, last_asked_at}]` |
| 说明 | 返回指定范围内学生高频问题 Top N。 |

## 5. 教师端错题类型统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/error-types` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date` |
| 返回参数 | `items[{error_type, count, ratio}]` |
| 说明 | 返回错题类型分布，用于图表展示。 |

## 6. 教师端薄弱知识点统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/weak-knowledge-points` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date`、`limit` |
| 返回参数 | `items[{knowledge_point_id, knowledge_point_name, wrong_count, qa_count, score}]` |
| 说明 | 综合错题次数和问答次数，返回薄弱知识点排名。 |

## 7. 教师教学建议生成接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/teaching-suggestion` |
| 请求方式 | POST |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date` |
| 返回参数 | `class_summary`、`top_risks`、`teaching_suggestions`、`recommended_exercises`、`follow_up_metrics` |
| 说明 | 聚合教师端统计数据，调用教师分析 Agent 生成教学建议。 |
