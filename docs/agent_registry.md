# Agent Registry

注册表位于 `agent_configs/registry.yaml`。在原有 provider、capabilities、input/output mapping、retrieval 和 fallback 字段之外，本次增加：

- `execution_mode`: `local | xingchen | hybrid | disabled`
- `local_handler`: 本地处理器的可导入路径；空值表示没有本地实现
- `priority`: 同等能力候选时的配置优先级
- `timeout_seconds`: 继续由 `provider.timeout_seconds` 提供

`GET /api/v1/workflows` 返回主要工作流的启用状态、Flow ID 是否配置、本地处理器状态和不可用原因。任一 Flow ID 缺失不会阻止应用启动。

| Agent | 模式 |
|---|---|
| GENERAL_QUESTION_V1 | local |
| ROUTER_01_FALLBACK_V1 | hybrid |
| LEARN_01_KNOWLEDGE_QA_V1 | hybrid |
| SOLVER_CT_V1 | hybrid |
| TEACH_01_LESSON_PREP_V1 | hybrid |
| TEACH_02_ASSIGNMENT_REVIEW_V1 | hybrid |
| RESEARCH_02_ACADEMIC_WRITING_V1 | hybrid |
| RESEARCH_03_DATA_ANALYSIS_V1 | hybrid |

`GENERAL_QUESTION_V1` 是低置信文本请求的最后一级本地模型能力。它只在专用业务 Agent 无法可靠确定、且星辰调度未获授权或不可用时执行；不调用星辰工作流、不伪造课程资料引用。模型输出达到长度上限时最多自动续写一次，模型不可用时返回明确的可重试提示而不让任务停在 `UNRESOLVED`。

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
| `DATA_ANALYSIS_LOCAL_V1` | 数据分析解释 | Spark 草稿 → Qwen3.5 归一 |

两段链的 Token 和耗时会合并计入一次内部 Agent 结果。结构校验失败不会自动切换模型再次生成，避免缺少业务字段时产生无上限重复调用；只有网络、限流和服务暂时不可用等 Provider 故障才按统一 ModelService 策略回退。

开发态可通过 `GET /api/v1/internal-agents` 查看注册项、模型路由和配置状态。该接口只读取本地配置，不发送模型请求。内部 Agent 保持 `subordinate_only`，不会直接注册为学生端顶层工作流；其中备课、作业初审、学术写作和数据分析已通过 `InternalAgentExecutionService` 适配到四个既有工作流。备课会接收同一次任务生成的本地 RAG 上下文；作业初审只把检索结果作为参考证据展示，不把答案注入批改输入，避免资料反向污染学生作答判断。

学生端 `/student` 与 `/workspace` 只展示“能力、知识增强、资料使用、检查状态”等产品语义，不展示 Provider、Flow ID、原始 Agent ID 或星辰实现。管理员仍可使用 `/debug`、`GET /api/v1/workflows` 和 Execution Debug 检查兼容链路。内部模型不可用时，后端可按注册表继续使用已配置的历史兼容能力，但不会把实现细节暴露到学生界面。
