# Agent Registry

注册表位于 `agent_configs/registry.yaml`。在原有 provider、capabilities、input/output mapping、retrieval 和 fallback 字段之外，本次增加：

- `execution_mode`: `local | disabled`
- `local_handler`: 本地处理器的可导入路径；空值表示没有本地实现
- `priority`: 同等能力候选时的配置优先级
- `timeout_seconds`: 继续由 `provider.timeout_seconds` 提供

`GET /api/v1/workflows` 返回主要 Runtime 的启用状态、本地处理器状态和不可用原因。Runtime 未就绪不会阻止应用启动，但任务会明确进入安全降级。

| Agent | 模式 |
|---|---|
| GENERAL_QUESTION_V1 | local |
| ROUTER_01_FALLBACK_V1 | local |
| LEARN_01_KNOWLEDGE_QA_V1 | local |
| SOLVER_CT_V1 | local |
| TEACH_01_LESSON_PREP_V1 | local |
| TEACH_02_ASSIGNMENT_REVIEW_V1 | local |
| RESEARCH_02_ACADEMIC_WRITING_V1 | local |
| RESEARCH_03_DATA_ANALYSIS_V1 | local |

`GENERAL_QUESTION_V1` 是日常通用问题和低置信文本请求的本地模型能力。没有课程领域线索、但带有“为什么、是什么、作用、区别”等明确常识问句时会直接进入该模块；其他专用业务 Agent 无法可靠确定时，也可作为最后一级本地能力。它按本地模型路由执行，模型不可用时进入确定性安全后备；不伪造课程资料引用。日常问题直接输出简洁自然语言并严格遵守用户的字数、受众和格式限制；模型输出达到长度上限时最多自动续写一次。

## 内部从属 Agent Hub

`InternalAgentHub` 是七个主要工作流之下的模型能力层，不是第二套路由器。它复用现有 `POST /api/v1/tasks`、TaskRunner、SSE 和检索上下文，当前注册 9 个内部 Agent：

| 内部 Agent | 任务 | 主链路 |
|---|---|---|
| `COURSE_CLASSIFIER_LOCAL_V1` | 课程编码分类 | Qwen3.5 JSON |
| `INTENT_CLASSIFIER_LOCAL_V1` | 用户意图分类 | Qwen3.5 JSON |
| `QUERY_REWRITER_LOCAL_V1` | RAG 查询改写 | Qwen3.5 JSON |
| `CIRCUIT_PLANNER_LOCAL_V1` | 电路求解规划 | Spark 草稿 → Qwen3.5 归一 |
| `CIRCUIT_VISION_EXTRACTOR_LOCAL_V1` | 电路图结构提取 | Qwen3.7 Vision JSON |
| `LESSON_PREP_LOCAL_V1` | 备课草稿 | Spark 草稿 → Qwen3.5 归一 |
| `ASSIGNMENT_REVIEW_LOCAL_V1` | 作业初审 | Spark 草稿 → Qwen3.5 归一 |
| `ACADEMIC_WRITING_LOCAL_V1` | 学术表达改写 | Spark 草稿 → Qwen3.5 归一 |
| `DATA_ANALYSIS_LOCAL_V1` | 模型主导数据分析 | Qwen 直接分析；按 `data_analysis_explanation` 路由失败时尝试 Spark |

两段链的 Token 和耗时会合并计入一次内部 Agent 结果。结构校验失败不会自动切换模型再次生成，避免缺少业务字段时产生无上限重复调用；只有网络、限流和服务暂时不可用等 Provider 故障才按统一 ModelService 策略回退。

开发态可通过 `GET /api/v1/internal-agents` 查看注册项、模型路由和配置状态。该接口只读取本地配置，不发送模型请求。内部 Agent 保持 `subordinate_only`，不会直接注册为学生端顶层工作流；其中备课、作业初审、学术写作和数据分析已通过 `InternalAgentExecutionService` 适配到四个既有工作流。备课会接收同一次任务生成的本地 RAG 上下文；作业初审只把检索结果作为参考证据展示，不把答案注入批改输入，避免资料反向污染学生作答判断。

学生端 `/student` 与 `/workspace` 只展示“能力、知识增强、资料使用、检查状态”等产品语义，不展示 Provider、敏感配置或原始 Agent ID。管理员仍可使用 `/debug`、`GET /api/v1/workflows` 和 Execution Debug 检查本地 Runtime 链路。内部模型不可用时，后端按注册表进入安全后备，但不会把实现细节暴露到学生界面。
