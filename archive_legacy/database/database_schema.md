# 数据库设计

## 设计原则

- 第一版优先支撑学生智能答疑、错题诊断、学习建议和教师端学情看板。
- 表结构保留后续扩展空间，例如班级、知识点层级、Agent 输出 JSON 和统计缓存。
- 业务主键使用自增 `BIGINT`，外部展示可通过编码字段完成。
- 所有时间字段采用数据库时间，后续接入后端时统一转换时区。
- 不在数据库中保存任何平台 API Key。

## 表关系概览

```text
user 1 --- n qa_record
user 1 --- n wrong_record
user 1 --- n learning_profile
course 1 --- n knowledge_point
course 1 --- n question
knowledge_point 1 --- n question
course 1 --- n teaching_statistics
```

## 1. user

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 用户 ID | BIGINT | 是 | 主键，自增 |
| username | 用户名 | VARCHAR(64) | 是 | 登录名或展示名 |
| display_name | 展示名称 | VARCHAR(64) | 否 | 前端显示名称 |
| role | 用户角色 | VARCHAR(32) | 是 | `student`、`teacher`、`admin` |
| class_id | 班级 ID | VARCHAR(64) | 否 | 学生所属班级或教师管理班级 |
| status | 用户状态 | VARCHAR(32) | 是 | `active`、`disabled` |
| created_at | 创建时间 | DATETIME | 是 | 记录创建时间 |
| updated_at | 更新时间 | DATETIME | 是 | 记录更新时间 |

## 2. course

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 课程 ID | BIGINT | 是 | 主键，自增 |
| course_code | 课程编码 | VARCHAR(64) | 是 | 唯一编码，如 `analog_electronics` |
| name | 课程名称 | VARCHAR(128) | 是 | 如模拟电子技术 |
| description | 课程说明 | TEXT | 否 | 课程简介 |
| term | 学期 | VARCHAR(64) | 否 | 如 `2026-spring` |
| status | 课程状态 | VARCHAR(32) | 是 | `active`、`archived` |
| created_at | 创建时间 | DATETIME | 是 | 记录创建时间 |
| updated_at | 更新时间 | DATETIME | 是 | 记录更新时间 |

## 3. knowledge_point

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 知识点 ID | BIGINT | 是 | 主键，自增 |
| course_id | 课程 ID | BIGINT | 是 | 关联 `course.id` |
| parent_id | 父知识点 ID | BIGINT | 否 | 支持知识点层级 |
| code | 知识点编码 | VARCHAR(64) | 是 | 如 `AE-001` |
| name | 知识点名称 | VARCHAR(128) | 是 | 知识点标题 |
| description | 知识点说明 | TEXT | 否 | 简要说明 |
| material_path | 资料路径 | VARCHAR(255) | 否 | 对应 Markdown 文件路径 |
| difficulty_level | 难度等级 | VARCHAR(32) | 否 | `basic`、`medium`、`advanced` |
| created_at | 创建时间 | DATETIME | 是 | 记录创建时间 |
| updated_at | 更新时间 | DATETIME | 是 | 记录更新时间 |

## 4. question

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 题目 ID | BIGINT | 是 | 主键，自增 |
| course_id | 课程 ID | BIGINT | 是 | 关联 `course.id` |
| knowledge_point_id | 知识点 ID | BIGINT | 否 | 关联 `knowledge_point.id` |
| question_type | 题型 | VARCHAR(64) | 是 | `concept`、`calculation`、`analysis`、`timing` |
| question_text | 题目内容 | TEXT | 是 | 题干 |
| reference_answer | 参考答案 | TEXT | 否 | 标准答案或答案要点 |
| difficulty | 难度 | VARCHAR(32) | 否 | `easy`、`medium`、`hard` |
| source | 来源 | VARCHAR(128) | 否 | 课件、作业、样例等 |
| created_at | 创建时间 | DATETIME | 是 | 记录创建时间 |
| updated_at | 更新时间 | DATETIME | 是 | 记录更新时间 |

## 5. qa_record

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 问答记录 ID | BIGINT | 是 | 主键，自增 |
| user_id | 用户 ID | BIGINT | 是 | 提问学生 |
| course_id | 课程 ID | BIGINT | 是 | 关联课程 |
| knowledge_point_id | 知识点 ID | BIGINT | 否 | 识别出的知识点 |
| question | 学生问题 | TEXT | 是 | 原始问题 |
| answer | Agent 回答 | TEXT | 是 | 回答正文 |
| agent_payload | Agent 原始输出 | JSON | 否 | 保存结构化回答 |
| confidence | 置信级别 | VARCHAR(32) | 否 | `high`、`medium`、`low` |
| need_more_information | 是否需补充信息 | BOOLEAN | 是 | 默认 false |
| created_at | 创建时间 | DATETIME | 是 | 提问时间 |

## 6. wrong_record

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 错题记录 ID | BIGINT | 是 | 主键，自增 |
| user_id | 用户 ID | BIGINT | 是 | 学生 |
| question_id | 题目 ID | BIGINT | 否 | 可关联 `question.id` |
| course_id | 课程 ID | BIGINT | 是 | 关联课程 |
| knowledge_point_id | 知识点 ID | BIGINT | 否 | 薄弱知识点 |
| question_text | 题目快照 | TEXT | 是 | 便于题库未入库时保存原题 |
| student_answer | 学生答案 | TEXT | 是 | 原始作答 |
| reference_answer | 参考答案 | TEXT | 否 | 参考答案快照 |
| diagnosis | 诊断摘要 | TEXT | 是 | Agent 输出摘要 |
| diagnosis_payload | 诊断结构化结果 | JSON | 否 | 保存错误类型、步骤和建议 |
| error_type | 主错误类型 | VARCHAR(128) | 否 | 如 `condition_missing` |
| priority | 优先级 | VARCHAR(32) | 否 | `high`、`medium`、`low` |
| created_at | 创建时间 | DATETIME | 是 | 提交时间 |

## 7. learning_profile

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 学习画像 ID | BIGINT | 是 | 主键，自增 |
| user_id | 用户 ID | BIGINT | 是 | 学生 |
| course_id | 课程 ID | BIGINT | 是 | 课程 |
| weak_points_json | 薄弱知识点 | JSON | 否 | 知识点、分数、证据 |
| study_plan_json | 学习计划 | JSON | 否 | 最近一次结构化学习计划 |
| mastery_score | 掌握度评分 | DECIMAL(5,2) | 否 | 0 到 100 |
| last_generated_at | 最近生成时间 | DATETIME | 否 | 最近一次学习建议生成时间 |
| updated_at | 更新时间 | DATETIME | 是 | 最近更新时间 |

## 8. teaching_statistics

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 统计 ID | BIGINT | 是 | 主键，自增 |
| course_id | 课程 ID | BIGINT | 是 | 课程 |
| class_id | 班级 ID | VARCHAR(64) | 否 | 班级 |
| stat_type | 统计类型 | VARCHAR(64) | 是 | `high_question`、`error_type`、`weak_point`、`activity` |
| stat_data | 统计数据 | JSON | 是 | 聚合结果 |
| stat_date | 统计日期 | DATE | 是 | 统计日期 |
| generated_by | 生成来源 | VARCHAR(64) | 否 | `system`、`teacher_agent` |
| created_at | 创建时间 | DATETIME | 是 | 生成时间 |

## 第一版索引建议

| 表 | 索引 | 用途 |
| --- | --- | --- |
| user | `idx_user_role_class` | 按角色和班级筛选 |
| knowledge_point | `uk_course_code` | 保证课程内知识点编码唯一 |
| question | `idx_question_course_kp` | 按课程和知识点查题 |
| qa_record | `idx_qa_user_course_time` | 学生历史问答查询 |
| wrong_record | `idx_wrong_course_kp_time` | 教师端薄弱知识点统计 |
| wrong_record | `idx_wrong_error_type` | 错题类型统计 |
| learning_profile | `uk_profile_user_course` | 每名学生每门课一份画像 |
| teaching_statistics | `idx_stats_course_type_date` | 教师端统计缓存查询 |
