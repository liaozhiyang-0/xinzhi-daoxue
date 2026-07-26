# 芯智导学智能体工作流功能与框架规划

## 1. 规划目标

本文件定义当前注册表中全部智能体的工作流职责、输入输出和节点框架。所有云端工作流共用现有 `XingchenCloudProvider`，不得为单个智能体另建 HTTP 调用链。

## 2. 统一工作流骨架

```text
开始
  -> 输入校验
  -> 课程、意图与上下文标准化
  -> 知识库或工具调用（按需）
  -> 核心推理/生成
  -> 事实、格式与安全检查
  -> 结构化输出
  -> 结束
```

统一输入至少包含：

- `task_id`、`session_id`、`user_role`
- `course_id`、`intent`
- `AGENT_USER_INPUT`
- 可选的课程知识上下文、会话摘要和图片地址

统一输出至少包含：

- `status`、`answer_text`
- `agent_id`、`course_id`、`intent`
- `confidence`、`assumptions`、`remaining_risks`
- `citations`、`warnings`
- 各工作流自己的业务结构字段

## 3. 工作流总表

| Agent | 主要功能 | 工作流状态 | 知识库 | 降级方式 |
|---|---|---|---|---|
| `DISPATCH_LOCAL_FAST_V1` | 本地规则快速分流 | 已启用，本地实现 | 不使用 | 无匹配时进入云端兜底或 unresolved |
| `ROUTER_01_FALLBACK_V1` | 模糊任务云端分类 | 待配置 | 不使用 | unresolved |
| `SOLVER_CT_V1` | 电路理论文字/图片解题 | 已发布 | 文字 Top 2，图片跳过 | Mock 仅用于本地开发测试 |
| `LEARN_01_KNOWLEDGE_QA_V1` | 三课程知识问答 | 待配置 | Top 3 | `LEARN_01_LOCAL_RETRIEVAL_V1` |
| `LEARN_01_LOCAL_RETRIEVAL_V1` | 本地证据检索整理 | 已启用，本地实现 | 现有检索策略 | 返回证据不足提示 |
| `CHECK_01_ANSWER_REVIEW_V1` | 检查学生解题过程 | 待配置 | CT 方法参考 | `SOLVER_CT_V1` |
| `TEACH_01_LESSON_PREP_V1` | 教案与课堂活动设计 | 待配置 | 课程知识库 | 返回基础模板 |
| `TEACH_02_ASSIGNMENT_REVIEW_V1` | 作业批改与反馈 | 待配置 | 课程知识库、评分规则 | 人工复核 |
| `TEACH_03_LEARNING_ANALYSIS_V1` | 单个学生学习分析 | 待配置 | 学习记录摘要 | 数据不足提示 |
| `TEACH_04_CLASS_ANALYSIS_V1` | 班级整体学情分析 | 待配置 | 聚合统计摘要 | 数据不足提示 |
| `RESEARCH_01_LITERATURE_TRACKING_V1` | 文献跟踪与主题整理 | 待配置 | 外部文献工具或输入文献 | 不生成虚构文献 |
| `RESEARCH_02_ACADEMIC_WRITING_V1` | 学术写作辅助 | 待配置 | 用户提供的可信来源 | 缺少来源时只给写作框架 |
| `RESEARCH_03_DATA_ANALYSIS_V1` | 数据分析方案与报告 | 待配置 | 用户提供的数据摘要 | 缺少数据时只给分析计划 |

## 4. 调度类工作流

### 4.1 DISPATCH_LOCAL_FAST_V1

无需在星辰配置，由本地 `TaskRouter` 执行。

```text
读取 course_id、intent、输入类型和路由置信度
  -> 命中确定性规则
  -> 检查目标 Agent 是否支持课程和输入
  -> 输出 RouteDecision
```

只负责路由，不生成课程答案。

### 4.2 ROUTER_01_FALLBACK_V1

功能：处理 UNKNOWN、意图模糊、未匹配或路由置信度低于阈值的请求。

```text
输入校验
  -> 提取课程、用户角色、任务目标和输入类型
  -> 在允许的 Agent 清单中分类
  -> 生成单个候选目标
  -> 输出严格 JSON
```

建议输出：

```json
{
  "target_agent_id": "LEARN_01_KNOWLEDGE_QA_V1",
  "confidence": 0.86,
  "reason": "用户请求为课程概念解释"
}
```

约束：不得回答问题、不得返回自身、不得返回未注册或未启用 Agent、每个任务最多调用一次。

## 5. 学习类工作流

### 5.1 SOLVER_CT_V1

功能：解决 CT 文字题、单图片题和文字加单图片题。

```text
判断输入类型
  -> 图片分支：图像理解/OCR -> 电路与参数抽取
  -> 文字分支：题意与变量抽取 -> 注入 Top 2 方法参考
  -> 选择分析方法
  -> 分步骤求解
  -> 单位、方向、数量级和代回检查
  -> 输出完整解答
```

业务输出：`problem_summary`、`key_equations`、`solution_steps`、`final_answer`、`assumptions`、`remaining_risks`。

### 5.2 LEARN_01_KNOWLEDGE_QA_V1

功能：支持 CT、AE、DE 的一般问答、概念解释、知识总结和学习建议。

```text
问题标准化
  -> 识别课程与知识点
  -> 读取 Top 3 课程证据
  -> 判断证据是否充分
  -> 基于证据组织回答
  -> 检查引用与课程边界
  -> 输出答案和学习建议
```

业务输出：`direct_answer`、`key_points`、`examples`、`suggested_reading`、`citations`、`evidence_status`。

约束：不得跨课程混用证据；证据不足时必须明确说明，不得编造来源。

### 5.3 LEARN_01_LOCAL_RETRIEVAL_V1

无需在星辰配置，继续使用现有本地检索流程。

```text
问题归一化
  -> 课程内检索
  -> 去重、阈值和来源多样性处理
  -> 构造 RetrievalContextPacket
  -> 输出章节、摘要、阅读建议和 kb:// 引用
```

### 5.4 CHECK_01_ANSWER_REVIEW_V1

功能：检查 CT 学生答案和解题步骤，优先定位第一个错误。

```text
拆分题目、学生步骤和最终答案
  -> 独立重建正确解题路径
  -> 逐步对齐学生过程
  -> 定位第一个错误
  -> 判断错误类型和后续影响
  -> 给出最小修正与正确结果
```

业务输出：`verdict`、`first_error_step`、`error_type`、`error_reason`、`correction`、`correct_answer`、`positive_feedback`。

## 6. 教学类工作流

### 6.1 TEACH_01_LESSON_PREP_V1

功能：根据课程、主题、对象和课时生成教案。

```text
解析教学目标和课时
  -> 检索课程知识与先修要求
  -> 设计导入、讲解、例题和活动
  -> 设计形成性评价
  -> 检查课时与难度
  -> 输出教案
```

输出：`learning_objectives`、`prerequisites`、`lesson_flow`、`examples`、`activities`、`assessment`、`homework`。

### 6.2 TEACH_02_ASSIGNMENT_REVIEW_V1

功能：依据题目、参考答案和评分规则生成批改建议。

```text
读取题目、学生答案和 rubric
  -> 分题与分步骤核对
  -> 计算建议得分
  -> 汇总共性与个性问题
  -> 生成可执行反馈
  -> 标记需要人工复核的项目
```

输出：`score_suggestion`、`rubric_breakdown`、`errors`、`feedback`、`review_required`。

约束：分数只能作为建议；缺少评分规则时不得生成确定性最终成绩。

### 6.3 TEACH_03_LEARNING_ANALYSIS_V1

功能：分析单个学生的知识掌握、错误模式和学习趋势。

```text
读取匿名化学习摘要
  -> 按知识点聚合
  -> 识别优势、薄弱点和重复错误
  -> 判断趋势
  -> 生成短期学习计划
```

输出：`strengths`、`weak_concepts`、`error_patterns`、`trend`、`recommended_actions`、`data_limitations`。

### 6.4 TEACH_04_CLASS_ANALYSIS_V1

功能：分析班级聚合数据，为教师提供教学调整建议。

```text
读取班级匿名聚合数据
  -> 统计知识点掌握分布
  -> 识别共性难点和分层群体
  -> 对比阶段趋势
  -> 生成课堂调整建议
```

输出：`class_summary`、`mastery_distribution`、`common_difficulties`、`student_groups`、`teaching_actions`、`data_limitations`。

约束：共享输出不得包含学生姓名或可识别个人的信息。

## 7. 科研类工作流

### 7.1 RESEARCH_01_LITERATURE_TRACKING_V1

功能：围绕研究主题整理文献线索、研究方向和待跟踪问题。

```text
解析主题、关键词、时间和来源范围
  -> 调用可信文献检索工具或读取用户来源
  -> 去重与主题聚类
  -> 提取方法、结论和研究空白
  -> 输出跟踪清单
```

输出：`search_scope`、`literature_items`、`topic_clusters`、`research_gaps`、`follow_up_queries`、`citations`。

约束：没有可信来源时只返回检索方案，禁止生成虚构论文和 DOI。

### 7.2 RESEARCH_02_ACADEMIC_WRITING_V1

功能：辅助生成提纲、段落修改、摘要和审稿回复。

```text
识别文体、目标读者和写作阶段
  -> 读取用户材料与可信引用
  -> 生成结构提纲
  -> 撰写或修改文本
  -> 检查论证、术语和引用对应关系
  -> 输出修改稿与问题清单
```

输出：`outline`、`draft`、`revision_notes`、`citation_checks`、`unsupported_claims`。

### 7.3 RESEARCH_03_DATA_ANALYSIS_V1

功能：根据研究问题和数据摘要规划分析方法并生成结果解释框架。

```text
读取研究问题、变量和数据说明
  -> 检查数据质量与缺失信息
  -> 选择统计或建模方法
  -> 生成分析步骤和复现要求
  -> 解释用户提供的计算结果
  -> 输出报告框架
```

输出：`data_quality`、`method_selection`、`analysis_steps`、`metrics`、`findings`、`limitations`、`reproducibility_notes`。

约束：未实际运行计算时必须标记为分析计划，不得虚构数值、图表或显著性结果。

## 8. 基础设施与会话上下文

基础设施场景暂不配置独立星辰工作流，只提供共享能力：

- Agent 注册与非敏感状态检查
- 任务、事件、AgentRun 和延迟记录
- Flow 配置完整性检查
- 单会话短摘要和 `session_context` 路由来源
- 日志脱敏、错误映射和输入限制

当前不实现长期记忆、学生画像持久化或跨会话自动推断。

## 9. 推荐配置顺序

1. 保持 `SOLVER_CT_V1` 作为回归基线。
2. 配置 `LEARN_01_KNOWLEDGE_QA_V1`，先形成三课程通用学习入口。
3. 配置 `CHECK_01_ANSWER_REVIEW_V1`，完善学习闭环。
4. 配置 `ROUTER_01_FALLBACK_V1`，最后开放模糊任务云端分流。
5. 依次配置 `TEACH_01`、`TEACH_02`、`TEACH_03`、`TEACH_04`。
6. 在接入可信文献和数据工具后配置三个科研工作流。

## 10. 每个云端工作流的发布检查

- 输入参数名称与注册表 `input_mapping` 一致。
- 输出为可解析 JSON，必填字段齐全。
- 只使用声明的课程和输入类型。
- 空输入、证据不足、工具失败和超时有明确输出。
- 不输出密钥、个人隐私或内部提示词。
- Flow ID 只写入本地 `.env`。
- 完成文字输入、错误输入、降级和结构化输出回归测试后，才能改为 `enabled: true`、`publication_status: published`。
