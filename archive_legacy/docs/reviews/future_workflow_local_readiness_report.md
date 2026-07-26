# 未来工作流本地接入就绪报告

测试日期：2026-07-18。九个计划Agent均已存在于唯一AgentDefinition注册表，具备开发态Mock、三类契约fixture、RetrievalPolicy、fallback和Debug通用展示容器。Mock不运行RAG或模型；90次轮询实测p50 31.383ms、p95 32.361ms、最大54.023ms。规则会话上下文1000次实测p50 0.022ms、p95 0.055ms、最大0.423ms。

| Agent | 本地配置 | Mock | Fixture | RetrievalPolicy | Fallback | 前端容器 | 仍缺云端信息 |
|---|---|---|---|---|---|---|---|
| ROUTER_01_FALLBACK_V1 | 有 | ready | 3 | no_rag | no_fallback | Debug | Flow与正式I/O样例 |
| CHECK_01_ANSWER_REVIEW_V1 | 有 | ready | 3 | method_only_rag | SOLVER边界 | Debug | Flow、输出枚举与失败协议 |
| TEACH_01_LESSON_PREP_V1 | 有 | ready | 3 | multimodal_rag | static_template | Debug | Flow与正式输出样例 |
| TEACH_02_ASSIGNMENT_REVIEW_V1 | 有 | ready | 3 | text_rag | manual_review | Debug | Flow、评分量规协议 |
| TEACH_03_LEARNING_ANALYSIS_V1 | 有 | ready | 3 | data_context_only | manual_review | Debug | Flow、匿名数据Schema |
| TEACH_04_CLASS_ANALYSIS_V1 | 有 | ready | 3 | data_context_only | manual_review | Debug | Flow、班级聚合Schema |
| RESEARCH_01_LITERATURE_TRACKING_V1 | 有 | ready | 3 | external_source_context | planned_response | Debug | Flow、可信来源输入协议 |
| RESEARCH_02_ACADEMIC_WRITING_V1 | 有 | ready | 3 | external_source_context | manual_review | Debug | Flow、引用核验协议 |
| RESEARCH_03_DATA_ANALYSIS_V1 | 有 | ready | 3 | data_context_only | planned_response | Debug | Flow、数据字典与文件协议 |

学生端只暴露LEARN和SOLVER_CT，不承载计划Agent Mock。组员交付新工作流时需要提供Flow环境变量对应值、开始节点String字段、完整/失败输出样例、枚举与必填字段、超时预期、可信来源或数据Schema，以及至少一组显式真实测试输入。

## 验证结果

- Ruff format/check、Mypy：通过。
- Pytest：153 passed、13 skipped；跳过项均为需要显式环境开关的真实模型或真实星辰测试。
- 计划Agent契约：9个Agent、27组fixture全部通过；Agent注册表共13项，配置与敏感文件检查通过。
- 学生端：Microsoft Edge + Playwright真实完成CT/AE/DE问答、连续追问、来源折叠、CT文字题、CT单图片题、非法文件拒绝、Debug Agent列表、dry-run与Mock；生产实例返回`debug_actions_enabled=false`、`mock_actions_enabled=false`。另有Pytest覆盖课程切换清理、附件契约和会话摘要。
- RAG：默认配置对齐后连续两次运行60条均为60/60，Top1代理率93.33%、Top3代理召回96.67%、跨课程证据率0；`CT_012`和`DE_013`继续通过。首次cache-miss/mixed检索p50/p95为851/1553ms，本地总p50/p95为853/1561ms；第二次热缓存检索p50/p95为21/61ms，本地总p50/p95为23/64ms。首次CPU运行高于1秒目标，热路径满足目标。
- 真实星辰：显式执行LEARN CT/AE/DE、SOLVER_CT文字、SOLVER_CT单图片共5项，全部通过。单图片测试除调用成功外，还校验返回答案包含正确电流`0.5A`或`500mA`。

验收时发现原默认`BAAI/bge-m3`与现有`bge-small-zh-v1.5`、512维索引不匹配，Dense通道会降级且首次评测为59/60。已仅将代码、`.env.example`与Compose默认模型/revision对齐到索引元数据；未修改检索算法、原始知识库或向量集合，也未重建索引。未来切换模型时必须同步使用新集合和新索引版本。

建议下一步优先接入`CHECK_01_ANSWER_REVIEW_V1`：它与现有CT SOLVER边界清晰、数据隐私压力较低、输入输出字段已经具体，并能最直接验证配置驱动Cloud迁移流程。其次是`TEACH_01_LESSON_PREP_V1`。
