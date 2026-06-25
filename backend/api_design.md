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

## 1. 学生识图解题接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/vision-solve` |
| 请求方式 | POST |
| 说明 | 调用识图解题 Agent，识别题图结构并返回分步解题结果。 |

### 请求参数

```json
{
  "user_id": "10001",
  "course_id": "01_circuit_theory",
  "chapter_hint": "第8章 一阶电路的暂态分析",
  "image_ids": ["file-vision-001"],
  "text_hint": "求 t>=0 时电容电压",
  "answer_style": "detailed"
}
```

### 返回参数

```json
{
  "solve_record_id": "vs-90001",
  "recognized_question": "RC 换路电路求电容电压。",
  "circuit_structure": {
    "nodes": ["A", "0"],
    "branches": ["R1 A-0", "C A-0"],
    "uncertain_items": []
  },
  "chapter": "第8章 一阶电路的暂态分析",
  "method": "三要素法",
  "key_equations": ["uC(t)=uC(inf)+[uC(0+)-uC(inf)]e^{-t/tau}"],
  "steps": ["识别换路前后状态", "求初值、终值和时间常数", "代入三要素公式"],
  "final_answer": "按题图参数得到的最终表达式",
  "mistake_warnings": ["注意电容电压连续", "时间常数中的 R 需要从电容端口看入"],
  "recommended_review": ["chapters/08_first_order_transient_analysis.md"]
}
```

## 2. 学生智能问答接口

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

## 3. 简单纠错接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/qa/error-hint` |
| 请求方式 | POST |
| 说明 | 调用课程问答 Agent 的简易纠错模块，返回轻量错因提示和复习建议。 |

### 请求参数

```json
{
  "user_id": "10001",
  "course_id": "01_circuit_theory",
  "chapter_hint": "第8章 一阶电路的暂态分析",
  "student_step": "我求时间常数时把受控源也置零。",
  "question_context": "含受控源的一阶 RC 电路求时间常数。"
}
```

### 返回参数

```json
{
  "hint_record_id": "eh-80001",
  "summary": "这一步主要问题是把受控源当成独立源置零。",
  "possible_reason_tags": [
    {
      "code": "dependent_source_zeroed_error",
      "evidence": "学生在求等效电阻时关闭了受控源。"
    }
  ],
  "student_friendly_explanation": "求含受控源电路的等效电阻时，独立源置零，受控源必须保留。",
  "next_step_hint": "请从电容端口加测试源，再列 KCL 求 Req。",
  "recommended_review": ["chapters/08_first_order_transient_analysis.md"]
}
```

## 4. 学习建议接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/student/study-suggestion` |
| 请求方式 | POST |
| 说明 | 聚合问答、题图解题、简单纠错和学习画像，调用学习规划 Agent 生成建议。 |

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

## 5. 教师端高频问题统计接口

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

## 6. 教师端错因标签统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/error-reason-tags` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date` |
| 说明 | 返回简单纠错和识图解题易错提醒中的错因标签分布，用于饼图或柱状图展示。 |

### 返回参数

```json
{
  "items": [
    {"reason_tag": "time_constant_error", "tag_name": "时间常数错误", "count": 12, "ratio": 0.32}
  ]
}
```

## 7. 教师端薄弱知识点统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/weak-knowledge-points` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date`、`limit` |
| 说明 | 综合问答次数、识图解题记录、错因提示和学习画像，返回薄弱知识点排名。 |

### 返回参数

```json
{
  "items": [
    {
      "knowledge_point_id": "DE-004",
      "knowledge_point_name": "建立时间与保持时间",
      "reason_tag_count": 15,
      "qa_count": 22,
      "score": 86.5
    }
  ]
}
```

## 8. 学生活跃度统计接口

| 项目 | 内容 |
| --- | --- |
| 接口路径 | `/api/v1/teacher/stats/activity` |
| 请求方式 | GET |
| 请求参数 | `course_id`、`class_id`、`start_date`、`end_date` |
| 说明 | 返回问答次数、识图解题次数、简单纠错次数和活跃学生数趋势。 |

### 返回参数

```json
{
  "items": [
    {
      "date": "2026-06-24",
      "qa_count": 45,
      "vision_solve_count": 20,
      "error_hint_count": 12,
      "active_student_count": 18
    }
  ]
}
```

## 9. 教师教学建议生成接口

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

1. 先实现学生识图解题接口，打通识图解题 Agent。
2. 实现学生智能问答接口，打通课程问答 Agent。
3. 实现简单纠错接口，并写入错因提示记录。
4. 基于问答、识图解题和错因提示记录实现学习建议接口。
5. 使用聚合 SQL 实现教师端统计接口。
6. 最后接入教师分析 Agent 生成教学建议。
