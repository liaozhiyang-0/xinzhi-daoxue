# RAG 质量改进报告

生成日期：2026-07-18
评测集：`apps/api/tests/fixtures/rag_eval_cases.json`，共 60 条（CT 15、AE 15、DE 15、边界/降级 15）。

## 1. 问题清单与修复

| severity | stage | problem / evidence | root cause | fix | regression |
|---|---|---|---|---|---|
| P0 | 配置 | LEARN 永远本地降级 | 注册项仍为 disabled/planned | 启用 published 注册项，保留 Flow 环境变量边界 | `test_learn_registry_is_published_with_complete_io_mapping` |
| P0 | Provider 输入 | 云端收不到独立 context 字段 | 只把问题与证据拼接进 `AGENT_USER_INPUT` | 9 字段独立字符串映射 | `test_learn_payload_uses_strings_and_separate_retrieval_context` |
| P0 | Provider 输出 | 真实回答被当成一段普通文本 | 云端发布版本采用 10 行结束协议 | JSON + 行协议双解析，answer/ref/request_id 统一映射 | `test_learn_published_line_protocol_is_parsed` |
| P0 | 降级 | 超时/HTTP 错误导致任务失败 | TaskRunner 无运行时 LEARN fallback | AppError 与云端 `status=failed` 均切换本地 LEARN，并标记原因 | 无效 Flow 正式任务实测 |
| P0 | 引用 | Provider 预先附加全部检索来源 | 没有依据云端 S 编号筛选 | 校验 inline 与声明引用，合法 S 映射为 `kb://`，S9 移除 | CitationValidator 单元测试、三课程真实测试 |
| P1 | 检索 | 电容连续性原文未进入候选 | 策略排除语料中的 `mixed/unknown` 类型 | 意图策略加入兼容类型，保留目标类型优先级 | CT 实测 Top1 变为“电容电压连续性” |
| P1 | 融合 | 单通道无关项与单通道相关项并列 | 纯 RRF 未利用标题/正文词项重合 | 增加小幅、确定性的标题与正文重合度加成 | 多模态 RRF 回归测试 |
| P1 | 性能 | 普通文本无条件加载图片模型与大 Reranker | 默认策略全开 | general_qa 图片为 0；Reranker 按单次开关，CPU 默认关闭；模型仍单例懒加载 | Debug 状态与真实运行 |
| P1 | 查询 | 礼貌前缀与短追问增加噪声 | 缺少统一查询重写 | 非 LLM 规则：NFKC、前缀清理、术语归一、短追问结合摘要 | query rewrite 单元测试 |
| P1 | 缓存 | 相同问题重复完成全链检索 | 只有 embedding cache | 新增结果 TTL/LRU cache，键包含课程、意图、策略、索引及模型版本 | Debug trace `cache_hit` |
| P2 | Debug | 只能看最终任务结果 | 无结构化调试 Trace | 限量内存 Trace、5 个 API、完整页面、A/B 与评测入口 | Debug API 测试与浏览器验收 |
| P2 | A/B | 云端关闭时 No RAG 侧又触发本地 fallback 检索 | 本地回答只能依赖检索，分支语义未显式区分 | 返回 `no_rag_no_cloud` 未运行结果；允许云端时才执行真实无 RAG 对照 | `test_rag_debug_compare_and_small_eval` |
| P2 | 测试客户端 | 中文问题变为 `?` | Windows PowerShell 5.1 管道默认编码 | 文档要求 UTF-8 bytes 或使用浏览器/Python HTTPX | 实际探针定位 |

## 2. 意图级 RetrievalPolicy

| policy | text K | image K | 主要类型 | 默认 Reranker |
|---|---:|---:|---|---|
| `learn_explain_concept` | 3 | 2 | concept、formula、method、chapter_summary；兼容 mixed/unknown | off |
| `learn_follow_up` | 3 | 1 | concept、formula、method；兼容 mixed/unknown | off |
| `learn_summarize` | 5 | 2 | chapter_summary、concept、method；兼容 mixed/unknown | off |
| `learn_advice` | 4 | 0 | chapter_summary、common_error、method；兼容 mixed/unknown | off |
| `learn_check_step` | 3 | 1 | formula、method、common_error；兼容 mixed/unknown | off |
| `learn_general_qa` | 配置值 | 0 | 不强制类型 | off |

每次 RetrievalResult 的 `trace.policy_name` 记录实际策略。SOLVER 策略保持冻结语义：只做方法参考，不将 RAG context 注入其生成链。

## 3. 60 条评测前后指标

这是一套检索代理评测，不把关键词或类型命中冒充完整答案正确率。57 条明确标记 `manual_review_required=true`。

| 指标 | 修复前实跑 | 修复后实跑 | 变化 |
|---|---:|---:|---:|
| 总通过 | 53/60 | 59/60 | +6 |
| 路由准确率 | 96.7% | 96.7% | 0 |
| course_id 准确率 | 100% | 100% | 0 |
| intent 准确率 | 100% | 100% | 0 |
| Top1 相关代理率 | 65.0% | 88.3% | +23.3 pp |
| Top3 召回代理率 | 85.0% | 95.0% | +10.0 pp |
| 跨课程证据率 | 0% | 0% | 0 |
| citation 合法率（本地/未运行云端口径） | 100% | 100% | 0 |
| citation 使用率 | 95.0% | 95.0% | 0 |
| p50 检索耗时 | 333 ms | 312 ms | -21 ms |
| p95 检索耗时 | 466 ms | 410 ms | -56 ms |
| p50 总耗时 | 336 ms | 314 ms | -22 ms |
| p95 总耗时 | 468 ms | 413 ms | -55 ms |

“修复前”与“修复后”均为本次会话中真实运行同一 60 条 fixture 的结果，后者是最终代码的再次实跑。修复后首次启动还包含模型冷启动，因此平均值不用于对比，p50/p95 更能表示热路径。离线评测返回 `misrouted_evaluated=0`、`misrouted_accuracy=null`，不会把未调用云端的结果冒充成误路由成绩；真实云端口径见 E2E 报告。

## 4. 真实云端质量

- CT/AE/DE：3/3 success；
- 证据引用：3/3 返回真实 S 编号；
- CitationValidator：3/3 passed；
- request_id：3/3 往返一致；
- 复杂整题：真实返回 misrouted；
- 空 context：真实测试不返回伪造 source reference；
- 无效 Flow：真实返回显式错误，并在正式 TaskRunner 中降级为 local。

## 5. CPU 与缓存结果

- BGE-small、SigLIP2、BGE reranker 都是进程内单例，不按请求重新下载或实例化；
- general_qa 默认不执行文本到图片检索；
- 图片模型只在意图策略与请求开关同时允许时加载；
- Reranker 默认关闭，可在 Debug 或任务 options 中单次启用；
- embedding cache 与 retrieval result cache 同时存在；
- Debug 页面显示 `cache_hit`、模型 loaded/lazy 和单次首次加载耗时；
- 真实 60 条热路径 p95 检索为 410 ms。

## 6. 剩余风险和下一步

1. `DE_013` 是唯一未通过当前 Top3 代理标签的案例，建议只调整 DE 同义词或对应章节的 content type，不要全局提高 Top K。
2. 代理指标不能替代教师对回答语义、公式和教学表达的评审。
3. 路由 96.7% 主要受 AE/DE 完整求解尚无专用 Solver 影响；不要把 LEARN 当成求解 Agent。
4. 云端真实样本仍少，应在不记录长教材正文和敏感信息的前提下积累匿名统计。
