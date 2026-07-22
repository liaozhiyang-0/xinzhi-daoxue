# 已完成工作流接入审计报告

审计日期：2026-07-20。注册表位置为 `agent_configs/registry.yaml`；Flow 只通过环境变量解析，值未写入本文。七个定义共用现有 `XingchenCloudProvider` 和同一连接池，没有新增 HTTP 客户端。

## 最终注册与真实状态

| Agent ID | Flow 环境变量 | 注册/运行状态 | Parser | RAG | Validator / Renderer | fallback | 真实最小检查 |
|---|---|---|---|---|---|---|---|
| `LEARN_01_KNOWLEDGE_QA_V1` | `XINGCHEN_KNOWLEDGE_QA_FLOW_ID` | enabled, published, configured | `json_or_fixed_line` | `text_rag` | `learn_qa` / `learn_qa` | 本地检索回答 | success，17,371 ms |
| `SOLVER_CT_V1` | `XINGCHEN_SOLVER_CT_FLOW_ID` | enabled, published, configured | `json` | `method_only_rag` | `solver_ct` / `solver_ct` | 无通用替代 | completed，44,453 ms |
| `TEACH_01_LESSON_PREP_V1` | `XINGCHEN_LESSON_PREP_FLOW_ID` | enabled, published, configured | `json` | `multimodal_rag` | `lesson_prep` / `lesson_prep` | 静态教案模板 | HTTP 200 但最终文本为空，解析失败，34,276 ms |
| `TEACH_02_ASSIGNMENT_REVIEW_V1` | `XINGCHEN_ASSIGNMENT_REVIEW_FLOW_ID` | enabled, published, configured | `json_or_fixed_line` | reference-only `text_rag` | `assignment_review` / `assignment_review` | 人工复核结果 | HTTP 200 但最终文本为空，解析失败，9,099 ms |
| `RESEARCH_02_ACADEMIC_WRITING_V1` | `XINGCHEN_ACADEMIC_WRITING_FLOW_ID` | enabled, published, configured | `json_or_fixed_line` | `external_source_context` | `academic_writing` / `academic_writing` | 人工复核 | completed，22,834 ms；纯文本解析，有 request_id 警告 |
| `RESEARCH_03_DATA_ANALYSIS_V1` | `XINGCHEN_DATA_ANALYSIS_FLOW_ID` | enabled, published, configured | `json_or_fixed_line` | `data_context_only` | `data_analysis` / `data_analysis` | 明确分析计划 | partial，24,875 ms；未提供数据时正确拒绝执行性结论 |
| `ROUTER_01_FALLBACK_V1` | `XINGCHEN_FALLBACK_ROUTER_FLOW_ID` | enabled, published, **未配置** | `json` | `no_rag` | `router_only` / `router_only` | unresolved | 未发送云端请求 |

真实检查命令：

```powershell
.\.venv\Scripts\python.exe scripts\validate_completed_workflows.py --live
```

合成输入不含隐私；报告不输出回答正文、Flow ID 或凭据。HTTP 200 只算传输成功，空回答仍判失败。

## 输入、输出与适配

LEARN 和冻结的 SOLVER 保持既有契约。四个新增业务接入使用本地逻辑输入契约，再由 `AgentInputMapper` 将课程、角色和用户真实材料确定性打包到已验证的 `AGENT_USER_INPUT`；TEACH_01 还保留仓库原有的 `course_id`、`retrieved_context`、`request_id`。这样不向星辰开始节点发送猜测字段；曾触发的 `study_design does not exist` 已通过该适配消除。

平台输出映射统一到 `status`、`answer_text`、`business_data`、warnings、confidence 与 request_id。专属 Validator 再检查引用、求解边界、教案结构、rubric 分数、虚构 DOI/事实和虚构统计量；Renderer 只消费校验后的结构。

## 审计结论

- 已完整本地接入：七个 AgentDefinition、路由、ExecutionPlan、Provider、Parser、Validator、Renderer、fallback、Debug 和前端 Presentation。
- 实际云端可用：LEARN、SOLVER、学术写作；数据分析在无材料用例下按设计返回 partial。
- 云端发布阻塞：TEACH_01 与 TEACH_02 的结束节点未向 API 返回最终 `choices[0].delta.content`；需在星辰控制台修正结束节点输出后重跑定向检查。
- 配置阻塞：Router Flow ID 缺失，因此低置信请求当前安全返回 unresolved。
- Mock：开发配置仍保留显式 `development.mock_profile`，正式 `enabled + published` 路径不把 Mock 结果描述为真实云端结果。
- 前端：正式工作台不再要求功能选择；Debug 页仍允许查看内部 Agent 和手动契约信息。

## 未达到的最终验收项

由于上述两个空回答和 Router 未配置，“七个真实云端回归全部通过”尚未达成，因此本报告不将整项工作标为完全验收。代码侧降级与 unresolved 行为已实现并测试，但不能替代云端发布修复。
