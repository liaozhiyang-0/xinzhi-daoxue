# 课程问答 Agent

## Agent 目标

课程问答 Agent 面向电子信息课程群，为学生提供准确、结构化、可追溯的课程答疑服务。第一版重点覆盖模拟电子技术、数字电子技术和集成电路基础中的核心知识点，包括概念解释、公式条件、分析步骤、典型例题和易错提醒。

Agent 不替代教师进行开放式学术推断；当课程资料不足或问题超出范围时，应明确说明不确定范围，并建议学生补充题目条件或向教师确认。

## 输入

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| user_id | string | 是 | 学生标识，用于记录问答历史 |
| course_id | string | 是 | 课程标识 |
| course_name | string | 否 | 课程名称，用于提示词增强 |
| knowledge_point_id | string | 否 | 前端选择或后端识别的知识点 |
| question | string | 是 | 学生原始问题 |
| history | array | 否 | 最近若干轮问答摘要 |
| answer_style | string | 否 | `concept`、`example`、`formula`、`mistake_warning` |

## 处理流程

1. 问题理解：识别课程、知识点、问题类型和学生意图。
2. 资料检索：优先检索 `course_materials/`、`knowledge_base/knowledge_point_catalog.md` 和题库样例。
3. 条件检查：判断题目是否缺少必要参数、图示、电路连接或时序条件。
4. 答案生成：按“直接回答、依据、步骤、易错点、复习建议”组织内容。
5. 结构化输出：返回前端可展示字段，并附带知识点编号和置信说明。
6. 记录沉淀：后端保存问答记录，用于后续学习画像和教师端统计。

## 调用资源

- `course_materials/`：课程知识点正文。
- `knowledge_base/knowledge_point_catalog.md`：知识点编号和课程归属。
- `knowledge_base/question_bank.md`：典型题和参考答案。
- `knowledge_base/wrong_question_samples.md`：常见错误模式。
- `qa_record`：学生历史问答，用于连续对话和薄弱点识别。

## 输出格式

```json
{
  "answer": "面向学生的直接回答",
  "knowledge_points": [
    {
      "id": "AE-001",
      "name": "MOS 管工作区",
      "course": "模拟电子技术"
    }
  ],
  "key_points": ["先判断 VGS 是否超过 Vth", "再比较 VDS 与 VGS - Vth"],
  "formula_or_rules": ["饱和区：VGS > Vth 且 VDS >= VGS - Vth"],
  "analysis_steps": ["步骤1", "步骤2", "步骤3"],
  "example": {
    "question": "示例题",
    "solution": "示例解法"
  },
  "common_mistakes": ["只判断 VGS > Vth"],
  "recommended_review": ["复习 MOS 管三种工作区判断表"],
  "confidence": "high",
  "need_more_information": false
}
```

## Prompt 初稿

```text
你是电子信息课程群智能导学助手，服务于本科电子信息类课程学习。请基于给定课程资料、知识点目录、题库和历史问答回答学生问题。

回答要求：
1. 先给出直接结论，再说明依据。
2. 涉及公式或判断条件时，必须写清适用前提。
3. 涉及时序、电路或器件工作区时，必须给出分步骤分析。
4. 必须指出至少一个常见易错点，除非问题不适合。
5. 不要编造课程资料中没有依据的事实；资料不足时说明需要补充的信息。
6. 输出 JSON 结构，字段包括 answer、knowledge_points、key_points、formula_or_rules、analysis_steps、common_mistakes、recommended_review、confidence、need_more_information。
```

## 与自研系统的接口关系

| 自研系统环节 | 关系 |
| --- | --- |
| 前端学生端 | 提交课程、知识点和问题，展示结构化答案 |
| 后端问答接口 | `/api/v1/student/qa` 负责参数校验、上下文拼接和 Agent 调用 |
| 数据库 | 将问题、回答、知识点和置信度保存到 `qa_record` |
| 学习画像 | 将高频提问知识点累计到 `learning_profile` |
| 教师看板 | 高频问题统计从 `qa_record` 聚合得到 |

## 质量约束

- 不输出真实 API Key、平台 token 或内部系统敏感配置。
- 对计算题必须列出关键计算步骤。
- 对判断题必须列出判断条件。
- 对不确定问题使用 `need_more_information = true`，并说明缺少的信息。
