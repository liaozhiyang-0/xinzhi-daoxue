# Cloud LEARN RAG 端到端实测报告

生成日期：2026-07-18
目标链路：本地知识库 → 多模态 RAG → `retrieved_context` → `XingchenCloudProvider` → `LEARN_01_KNOWLEDGE_QA_V1` → CitationValidator → 正式任务结果

## 1. 配置与契约现状

| 项目 | 初始状态 | 修正后状态 |
|---|---|---|
| Flow ID | 本机 `.env` 已存在，但不显示实际值 | `XINGCHEN_KNOWLEDGE_QA_FLOW_ID` 读取成功，仅暴露 `flow_configured=true` |
| 注册项 | `enabled=false`、`publication_status=planned` | `enabled=true`、`publication_status=published` |
| 正式路由 | 因注册项不可用而提前降级到本地 LEARN | CT/AE/DE 学习问答选择云端 `LEARN_01_KNOWLEDGE_QA_V1` |
| 输入映射 | 仅 `text -> AGENT_USER_INPUT` | 9 个字符串输入全部映射，问题与 `retrieved_context` 分离 |
| 输出映射 | 无 | 10 个结束节点字段完整映射 |
| 云端输出格式 | 本地假定为 JSON | 实测为按固定顺序换行的 10 字段协议，Provider 已兼容 JSON 与行协议 |

输入字段：`AGENT_USER_INPUT`、`question`、`course_id`、`intent`、`retrieved_context`、`previous_answer_summary`、`conversation_summary`、`response_depth`、`request_id`。

输出字段：`status`、`course_id`、`intent`、`answer`、`key_points_json`、`source_references_json`、`warnings_json`、`confidence`、`parse_status`、`request_id`。

所有输入在 Provider 边界转换为字符串；JSON 数组输出被解析为本地列表。API Key、Secret、Authorization 和 Flow ID 实值未写入日志、页面或本报告。

## 2. 运行环境健康检查

实测 `GET /api/v1/knowledge/health` 与 Debug 状态：

- Provider：`xingchen`，available；
- LEARN：enabled / published，Flow configured；
- 文本模型：`BAAI/bge-small-zh-v1.5`，CPU，512 维；
- 图片模型：`google/siglip2-base-patch16-224`，CPU，768 维，按需加载；
- Reranker：`BAAI/bge-reranker-v2-m3`，默认低延迟请求不加载；
- Qdrant：local persistent，connected；
- 文本 points：12,760；
- 图片 points：2,207；
- 索引版本：`RAG_f4e223885aa4c5a003d0`。

## 3. 正式任务 API 三课程真实结果

以下请求均由 `POST /api/v1/tasks` 创建，不是 Mock，也不是 Debug 专用聊天入口。

| 课程 | 问题 | task_id | RAG / Evidence | 检索 ms | 云端 ms | 总 ms | 云端引用 | 校验 | 最终引用 |
|---|---|---|---|---:|---:|---:|---|---|---|
| CT | 为什么电容电压不能突变？ | `task_2a7fa40f91654bb38a21698dfaf8ac0e` | ready / partial | 839 | 20,886 | 21,785 | S1、S2 | passed | 2 个第七章 CT `kb://` 来源 |
| AE | 为什么负反馈能稳定放大倍数？ | `task_8bae93045a3b471e8a586400c258e469` | ready / partial | 264 | 18,719 | 19,048 | S2、S3 | passed | 2 个 AE `kb://` 来源 |
| DE | 锁存器和触发器有什么区别？ | `task_76aff2d41ee44ef9a070c2d99693e99a` | ready / sufficient | 244 | 23,644 | 23,937 | S2 | passed | `kb://DE/...#chunk-89` |

三次有效请求：云端成功率 100%（3/3），完整 RAG grounding 成功率 100%（3/3），非法引用率 0%，本地降级率 0%。云端延迟 p50 为 20,886 ms，三次样本中的最大值为 23,644 ms。样本量较小，不能代表长期 SLA。

## 4. `retrieved_context` 与证据使用

发送给云端的上下文结构示例（正文截短）：

```text
evidence_status: partial
retrieval_mode: multimodal_hybrid_rrf_v2
rag_status: ready
index_version: RAG_f4e223885aa4c5a003d0

[S1]
课程：电路理论
章节：第七章
标题：2. 电容电压连续性
来源：kb://CT/课本/.../第七章.md#chunk-90
内容：电容电流为有限值时，电容电压连续……
```

验证结论：

1. 请求体中真实存在 `[S1]`；
2. 云端 CT 返回 `source_references_json=["S1","S2"]`；
3. S1、S2 均属于本次 Packet，而非后补或伪造；
4. CitationValidator 将 S1、S2 映射回本地两条 `kb://CT/...`；
5. AE、DE 也完成相同往返；
6. `request_id` 三次均原值返回。

因此三次请求同时满足 `cloud_answer_success=true` 与 `rag_grounding_success=true`。

## 5. 复杂任务边界

正式任务 `task_d818874ce817406ebfb08a44f5c44f94` 以学习问答意图提交“含受控源的一阶电路完整列方程并求全响应”，云端真实返回：

```text
status=misrouted
```

云端没有继续完成整题计算。另通过显式真实测试以 `intent=solve_problem` 直连同一统一 Provider，确认返回 `status=misrouted`、`intent=solve_problem`。冻结的 `SOLVER_CT_V1` 未修改。

## 6. 真实失败与本地降级

故障注入使用无效 Flow ID 启动独立本地实例，再经正式任务 API 请求，结果：

- task：`task_b8fe284b122e490eb133cadb2b3a4b82`；
- 上游错误：`xingchen_http_error`；
- 最终 Agent：`LEARN_01_LOCAL_RETRIEVAL_V1`；
- 最终 Provider：`local`；
- `fallback_used=true`；
- `fallback_reason=xingchen_http_error`；
- `cloud_status=cloud_failed`；
- 本地 RAG：ready；
- 本地 citation：3 个；
- 回答明确声明“不是讯飞星辰模型生成的正式回答”。

有效流量样本的失败率为 0/3；将一次故意无效 Flow 注入计入则为 1/4，且该次 100% 正确降级。两组口径必须分开理解。

## 7. 实测中发现的问题

1. 云端结束节点不是 JSON，而是换行字段；已增加兼容解析。
2. Windows PowerShell 5.1 直接把未编码的中文管道请求变成 `?`，会导致云端判定问题为空；这是测试客户端编码问题。浏览器和 Python HTTPX 的 UTF-8 请求正常。指南给出安全调用方式。
3. 云端返回 `failed` 状态时，原任务仍会标记云端完成；现已将语义失败也纳入本地降级。
4. `misrouted` 不要求证据引用，因此不再错误触发“缺少引用”。
5. 初始内容类型过滤遗漏真实语料中大量 `mixed/unknown` 块；已修正策略并加入标题/正文轻量重合度。

## 8. 尚未解决

- 60 条评测中 `DE_013`（施密特触发器回差）仍未达到当前 Top3 代理标签，需要人工检查原始资料覆盖、分块标题与同义词配置。
- 云端成功率与延迟样本仍小，需要持续记录真实任务而非把 3 次结果当作长期指标。
- AE/DE `solve_problem` 当前正式路由仍是未解析边界；本轮未扩充求解 Agent，避免改变既有路由范围。

## 9. 最终自动化验证

- `ruff check .`：通过；
- `ruff format --check apps/api/app apps/api/tests scripts`：通过；
- `mypy apps/api/app`：67 个源文件，无错误；
- 普通测试：122 passed，8 skipped；
- 真实 BGE-small / SigLIP2 模型测试：2 passed；
- 真实星辰专项：6 passed（68.68 秒）；
- 浏览器验收：状态、真实本地检索、分阶段时间线、Packet、context、fallback 和引用区域均可见。

调试站点验收截图：[`rag_debug_site_screenshot.png`](rag_debug_site_screenshot.png)。
