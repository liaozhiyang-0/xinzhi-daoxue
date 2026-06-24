# 错题诊断 Agent

## Agent 目标

错题诊断 Agent 用于分析学生作答与参考答案之间的差异，识别错误类型、缺失步骤和薄弱知识点，并给出可执行的修正建议。第一版重点服务电子信息课程中的条件判断类、公式应用类、时序分析类和概念辨析类错题。

Agent 的核心目标不是简单给出标准答案，而是解释“为什么错、错在哪里、下一步怎么补”。

## 输入

| 字段 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| user_id | string | 是 | 学生标识 |
| course_id | string | 是 | 课程标识 |
| knowledge_point_id | string | 否 | 知识点标识 |
| question_text | string | 是 | 题目内容 |
| student_answer | string | 是 | 学生作答 |
| reference_answer | string | 否 | 参考答案或答案要点 |
| scoring_rubric | array | 否 | 分步评分点，后续扩展 |
| previous_wrong_records | array | 否 | 学生历史错题摘要 |

## 处理流程

1. 题目解析：识别题目考查知识点、已知条件和目标结论。
2. 答案对比：对比学生答案与参考答案的结论、公式、条件和步骤。
3. 错误归类：将错误归入可统计类别，便于教师端看板聚合。
4. 原因解释：用学生能理解的语言说明错误原因。
5. 修正路径：给出正确解题步骤和关键判断点。
6. 学习建议：根据错误类型推荐复习资料和练习方向。
7. 数据回写：后端保存诊断结果，并更新学习画像。

## 错误类型建议

| 错误类型 | 说明 | 示例 |
| --- | --- | --- |
| condition_missing | 判断条件遗漏 | MOS 饱和区只判断 `VGS > Vth` |
| concept_confusion | 概念混淆 | 将触发器和锁存器混淆 |
| formula_misuse | 公式误用 | 将建立时间公式用于保持时间 |
| sign_direction_error | 符号或方向错误 | NMOS/PMOS 电压方向混用 |
| step_missing | 解题步骤缺失 | 未先求静态工作点 |
| timing_edge_error | 时钟边沿判断错误 | D 触发器输出随 D 实时变化 |
| calculation_error | 数值计算错误 | 代入正确但计算结果错误 |

## 调用资源

- `knowledge_base/wrong_question_samples.md`：错题诊断样例。
- `knowledge_base/question_bank.md`：参考题与答案要点。
- `course_materials/`：相关知识点讲义。
- `wrong_record`：历史错题，用于识别重复错误。
- `learning_profile`：学生薄弱知识点列表。

## 输出格式

```json
{
  "diagnosis_summary": "该答案遗漏了 MOS 饱和区的 VDS 判断条件。",
  "is_correct": false,
  "error_types": [
    {
      "code": "condition_missing",
      "name": "判断条件遗漏",
      "evidence": "学生只写出 VGS > Vth"
    }
  ],
  "related_knowledge_points": [
    {
      "id": "AE-001",
      "name": "MOS 管工作区"
    }
  ],
  "missing_steps": ["未比较 VDS 与 VGS - Vth"],
  "correct_solution_outline": ["先判断 VGS > Vth", "再判断 VDS >= VGS - Vth", "给出工作区结论"],
  "student_friendly_explanation": "VGS > Vth 只能说明 MOS 管导通，不能单独说明它处于饱和区。",
  "review_suggestions": ["整理 MOS 管截止区、线性区和饱和区判断表", "完成 3 道工作区判断题"],
  "priority": "high"
}
```

## Prompt 初稿

```text
你是电子信息课程错题诊断助手。请根据题目、学生答案、参考答案和课程知识点，对学生错误进行诊断。

诊断要求：
1. 先判断学生答案是否正确。
2. 若错误，必须指出错误类型、证据、缺失步骤和正确解题路径。
3. 错误类型必须使用给定分类，便于系统统计。
4. 解释要面向学生，避免只输出教师式评分。
5. 建议要具体到知识点和练习方式。
6. 若参考答案不足，请基于课程资料谨慎判断，并标记不确定范围。
7. 输出 JSON 结构，字段包括 diagnosis_summary、is_correct、error_types、related_knowledge_points、missing_steps、correct_solution_outline、student_friendly_explanation、review_suggestions、priority。
```

## 与自研系统的接口关系

| 自研系统环节 | 关系 |
| --- | --- |
| 前端学生端 | 提交题目、学生答案和参考答案，展示诊断结果 |
| 后端错题接口 | `/api/v1/student/wrong-question/diagnose` 负责调用 Agent |
| 数据库 | 将错误类型、知识点和诊断内容保存到 `wrong_record` |
| 学习画像 | 将重复错误和薄弱知识点汇总到 `learning_profile` |
| 教师看板 | 错题类型分布和薄弱知识点统计来自 `wrong_record` |

## 质量约束

- 不简单输出“答案错误”，必须说明证据。
- 不将所有错误归为“概念不清”，应细化为可统计类型。
- 不使用羞辱性评价，反馈应面向改进。
- 若题目条件不足，必须提示需要补充的条件。
