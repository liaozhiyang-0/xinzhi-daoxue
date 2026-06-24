# 数据库设计

## 1. user

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 用户 ID | BIGINT | 是 | 主键，自增 |
| username | 用户名 | VARCHAR(64) | 是 | 登录名或展示名 |
| role | 用户角色 | VARCHAR(32) | 是 | student、teacher、admin |
| class_id | 班级 ID | VARCHAR(64) | 否 | 学生所属班级 |
| created_at | 创建时间 | DATETIME | 是 | 记录创建时间 |

## 2. course

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 课程 ID | BIGINT | 是 | 主键，自增 |
| course_code | 课程编码 | VARCHAR(64) | 是 | 唯一编码 |
| name | 课程名称 | VARCHAR(128) | 是 | 如模拟电子技术 |
| description | 课程说明 | TEXT | 否 | 课程简介 |
| created_at | 创建时间 | DATETIME | 是 | 记录创建时间 |

## 3. knowledge_point

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 知识点 ID | BIGINT | 是 | 主键，自增 |
| course_id | 课程 ID | BIGINT | 是 | 关联 course |
| code | 知识点编码 | VARCHAR(64) | 是 | 如 AE-001 |
| name | 知识点名称 | VARCHAR(128) | 是 | 知识点标题 |
| description | 知识点说明 | TEXT | 否 | 简要说明 |

## 4. question

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 题目 ID | BIGINT | 是 | 主键，自增 |
| course_id | 课程 ID | BIGINT | 是 | 关联 course |
| knowledge_point_id | 知识点 ID | BIGINT | 否 | 关联 knowledge_point |
| question_text | 题目内容 | TEXT | 是 | 题干 |
| reference_answer | 参考答案 | TEXT | 否 | 标准答案或要点 |
| difficulty | 难度 | VARCHAR(32) | 否 | easy、medium、hard |

## 5. qa_record

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 问答记录 ID | BIGINT | 是 | 主键，自增 |
| user_id | 用户 ID | BIGINT | 是 | 提问学生 |
| course_id | 课程 ID | BIGINT | 是 | 关联课程 |
| knowledge_point_id | 知识点 ID | BIGINT | 否 | 识别出的知识点 |
| question | 学生问题 | TEXT | 是 | 原始问题 |
| answer | Agent 回答 | TEXT | 是 | 回答正文 |
| created_at | 创建时间 | DATETIME | 是 | 提问时间 |

## 6. wrong_record

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 错题记录 ID | BIGINT | 是 | 主键，自增 |
| user_id | 用户 ID | BIGINT | 是 | 学生 |
| question_id | 题目 ID | BIGINT | 否 | 可关联 question |
| course_id | 课程 ID | BIGINT | 是 | 关联课程 |
| knowledge_point_id | 知识点 ID | BIGINT | 否 | 薄弱知识点 |
| student_answer | 学生答案 | TEXT | 是 | 原始作答 |
| diagnosis | 诊断结果 | TEXT | 是 | Agent 输出摘要 |
| error_type | 错误类型 | VARCHAR(128) | 否 | 条件遗漏、概念混淆等 |
| created_at | 创建时间 | DATETIME | 是 | 提交时间 |

## 7. learning_profile

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 学习画像 ID | BIGINT | 是 | 主键，自增 |
| user_id | 用户 ID | BIGINT | 是 | 学生 |
| course_id | 课程 ID | BIGINT | 是 | 课程 |
| weak_points_json | 薄弱知识点 | JSON | 否 | 薄弱知识点及分数 |
| suggestion_json | 学习建议 | JSON | 否 | 最近一次建议 |
| updated_at | 更新时间 | DATETIME | 是 | 最近更新时间 |

## 8. teaching_statistics

| 字段名 | 字段含义 | 数据类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | 统计 ID | BIGINT | 是 | 主键，自增 |
| course_id | 课程 ID | BIGINT | 是 | 课程 |
| class_id | 班级 ID | VARCHAR(64) | 否 | 班级 |
| stat_type | 统计类型 | VARCHAR(64) | 是 | high_question、error_type、weak_point 等 |
| stat_data | 统计数据 | JSON | 是 | 聚合结果 |
| stat_date | 统计日期 | DATE | 是 | 统计日期 |
| created_at | 创建时间 | DATETIME | 是 | 生成时间 |
