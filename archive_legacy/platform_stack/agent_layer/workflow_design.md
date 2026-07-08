# Agent 工作流设计

## 1. 分流规则

1. 输入包含图片、截图或电路图，路由到识图解题 Agent。
2. 输入是课程概念问题，路由到课程问答 Agent。
3. 输入包含“怎么复习”“学习计划”等意图，路由到学习规划 Agent。
4. 输入包含“班级统计”“薄弱点”“教师分析”等意图，路由到教师分析 Agent。
5. 输入是解题过程追问，根据上下文回到识图解题 Agent 或课程问答 Agent。

## 2. 工作流伪代码

```text
if input.has_image:
    route_to("vision_solver_agent")
elif input.intent in ["concept_qa", "formula_condition", "simple_error_explanation"]:
    route_to("course_qa_agent")
elif input.intent == "learning_plan":
    route_to("learning_plan_agent")
elif input.intent == "teacher_analysis":
    route_to("teacher_analysis_agent")
else:
    route_to("course_qa_agent")
```

## 3. Agent 关系

- 识图解题 Agent 可以调用课程知识库，用于章节判断、公式检索和复习建议。
- 课程问答 Agent 可以调用错因标签作为辅助，用于简单纠错和易错提醒。
- 学习规划 Agent 使用学生历史问题、识图解题记录和薄弱知识点。
- 教师分析 Agent 使用班级统计数据和错因/知识点分布。

## 4. 追问处理

| 上下文 | 追问示例 | 处理方式 |
|---|---|---|
| 上一轮为识图解题 | “为什么这里用节点法？” | 回到识图解题 Agent，保留电路结构上下文。 |
| 上一轮为概念问答 | “这个公式什么时候不能用？” | 课程问答 Agent 继续解释。 |
| 学生追问某一步错误 | “我把受控源置零为什么不对？” | 课程问答 Agent 简易纠错模块解释。 |
| 学生要求重新看图 | “图里 R2 我刚才传错了” | 识图解题 Agent 重新解析。 |

## 5. 输出记录

每次路由应记录：

- 用户输入类型；
- 命中的意图；
- 路由 Agent；
- 使用的课程和章节；
- 是否调用图片解析；
- 是否生成错因提示；
- 是否需要人工或学生补充信息。

