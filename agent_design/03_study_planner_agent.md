# 学习规划 Agent

## Agent 目标

学习规划 Agent 根据学生问答历史、错题记录、薄弱知识点和可用复习时间，生成具体、可执行、可跟踪的学习建议。第一版重点输出短周期复习计划，服务学生端“学习建议区”。

Agent 应避免空泛鼓励，重点给出“先复习什么、为什么、怎么练、如何验证是否掌握”。

## 输入

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| user_id | string | 是 | 学生标识 |
| course_id | string | 是 | 课程标识 |
| weak_points | array | 是 | 薄弱知识点及分数 |
| wrong_records | array | 否 | 近期错题摘要 |
| qa_history | array | 否 | 近期问答摘要 |
| learning_goal | string | 否 | 学生目标，如“期末复习” |
| available_days | integer | 否 | 可用复习天数，默认 7 |
| daily_minutes | integer | 否 | 每日可投入时间 |

## 处理流程

1. 汇总证据：统计近期错题、提问频率和薄弱知识点。
2. 判断优先级：根据错误频次、知识点基础性和课程先修关系排序。
3. 制定计划：按天或按阶段生成学习任务。
4. 匹配练习：为每个薄弱点推荐题型、例题和检查方式。
5. 设置验证标准：说明完成任务后如何判断是否掌握。
6. 输出提醒：提示可能影响后续学习的风险点。

## 调用资源

- `learning_profile`：薄弱知识点、历史建议和掌握度。
- `wrong_record`：错题类型、知识点和诊断摘要。
- `qa_record`：高频提问和问答主题。
- `knowledge_base/knowledge_point_catalog.md`：知识点先后关系和课程归属。
- `course_materials/`：复习资料来源。

## 输出格式

```json
{
  "overall_assessment": "学生当前主要薄弱点集中在条件判断和时序分析。",
  "priority_knowledge_points": [
    {
      "id": "AE-001",
      "name": "MOS 管工作区",
      "priority": 1,
      "reason": "近期错题中多次遗漏饱和区 VDS 条件"
    }
  ],
  "study_plan": [
    {
      "day": 1,
      "theme": "MOS 管工作区判断",
      "tasks": ["整理三种工作区条件表", "完成 3 道判断题", "复盘错题原因"],
      "expected_output": "能独立写出截止区、线性区和饱和区判断流程",
      "estimated_minutes": 45
    }
  ],
  "practice_suggestions": ["优先练习条件判断题，再做综合电路题"],
  "mastery_checks": ["随机给出 VGS、VDS、Vth 时能在 1 分钟内判断工作区"],
  "risk_reminders": ["如果仍只记单个公式，后续放大电路静态工作点分析会继续失分"]
}
```

## Prompt 初稿

```text
你是电子信息课程学习规划助手。请根据学生的错题记录、问答历史、薄弱知识点和可用时间，生成结构化学习计划。

规划要求：
1. 必须说明优先复习顺序及原因。
2. 每个学习任务要可执行，避免“多复习、多练习”等空泛表达。
3. 每个阶段要给出可验证的掌握标准。
4. 建议应结合电子信息课程特点，如公式条件、时序图、电路分析步骤和典型题型。
5. 若输入数据不足，请输出基础复习方案，并标记依据不足。
6. 输出 JSON 结构，字段包括 overall_assessment、priority_knowledge_points、study_plan、practice_suggestions、mastery_checks、risk_reminders。
```

## 与自研系统的接口关系

| 自研系统环节 | 关系 |
| --- | --- |
| 前端学生端 | 展示优先知识点、每日任务、练习建议和掌握检查 |
| 后端学习建议接口 | `/api/v1/student/study-suggestion` 聚合学习画像后调用 Agent |
| 数据库 | 读取 `qa_record`、`wrong_record`、`learning_profile`，并回写最新建议 |
| 教师看板 | 可将班级层面的高频薄弱点提供给教师分析 Agent |

## 质量约束

- 计划必须与输入证据一致，不凭空假设学生水平。
- 每日任务不宜过多，需适合第一版演示和真实学习场景。
- 对薄弱知识点给出优先级和原因，便于前端排序展示。
- 不输出真实学生隐私信息。
